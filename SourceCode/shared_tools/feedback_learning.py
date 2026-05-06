from __future__ import annotations

import json
import math
import shutil
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path
from threading import Lock
from typing import Any

from shared_tools.db import connect, row_to_dict, transaction
from shared_tools.migrations import initialize_database
from shared_tools.inference_router import InferenceRouter
from shared_tools.ollama_client import OllamaClient


ORIGIN_MANUAL_FEEDBACK = "manual_feedback"
ORIGIN_OUTBOX_FEEDBACK = "outbox_feedback"
ORIGIN_REFLECTION = "reflection"
ORIGIN_CLOUD_CRITIQUE = "cloud_critique"
VALID_ORIGIN_TYPES = {
    ORIGIN_MANUAL_FEEDBACK,
    ORIGIN_OUTBOX_FEEDBACK,
    ORIGIN_REFLECTION,
    ORIGIN_CLOUD_CRITIQUE,
}
APPROVABLE_ORIGIN_TYPES = {
    ORIGIN_MANUAL_FEEDBACK,
    ORIGIN_OUTBOX_FEEDBACK,
    ORIGIN_REFLECTION,
}
GUIDANCE_ORIGIN_TYPES = {
    ORIGIN_MANUAL_FEEDBACK,
    ORIGIN_OUTBOX_FEEDBACK,
    ORIGIN_REFLECTION,
}
REVIEW_ONLY_ORIGIN_TYPES = {
    ORIGIN_REFLECTION,
    ORIGIN_CLOUD_CRITIQUE,
}
NEVER_APPROVE_ORIGIN_TYPES = {
    ORIGIN_CLOUD_CRITIQUE,
}


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _clamp_score(value: float) -> float:
    return max(0.0, min(1.0, value))


_LESSON_TTL_DAYS: dict[str, int] = {
    ORIGIN_MANUAL_FEEDBACK: 180,
    ORIGIN_OUTBOX_FEEDBACK: 90,
    ORIGIN_REFLECTION: 60,
    ORIGIN_CLOUD_CRITIQUE: 60,
}


def _expires_iso(origin_type: str) -> str:
    days = _LESSON_TTL_DAYS.get(origin_type, 90)
    return (datetime.now(timezone.utc) + timedelta(days=days)).isoformat()


class FeedbackLearningEngine:
    VALID_LANES = {"research", "ui", "personal", "project"}
    VALID_SOURCES = {"codex"}
    VALID_STATUSES = {"candidate", "approved", "rejected", "expired"}
    VALID_ORIGIN_TYPES = VALID_ORIGIN_TYPES
    APPROVABLE_ORIGIN_TYPES = APPROVABLE_ORIGIN_TYPES
    GUIDANCE_ORIGIN_TYPES = GUIDANCE_ORIGIN_TYPES
    REVIEW_ONLY_ORIGIN_TYPES = REVIEW_ONLY_ORIGIN_TYPES
    NEVER_APPROVE_ORIGIN_TYPES = NEVER_APPROVE_ORIGIN_TYPES
    INCOMPLETE_TOKEN = "__OATHWEAVER_OUTBOX_INCOMPLETE__"
    GUIDANCE_CANDIDATE_FALLBACK_MIN_CONFIDENCE = 0.8

    def __init__(
        self,
        repo_root: Path,
        *,
        client: OllamaClient | None = None,
        model_cfg: dict[str, Any] | None = None,
    ) -> None:
        self.repo_root = repo_root
        self.client = client or InferenceRouter(repo_root)
        self.model_cfg = model_cfg or {}

        self.learning_dir = repo_root / "Runtime" / "learning"
        self.handoff_root = repo_root / "Runtime" / "handoff"

        self.outbox_dirs = {
            "codex": self.handoff_root / "codex" / "outbox",
        }
        self.processed_dirs = {
            "codex": self.handoff_root / "codex" / "outbox_processed",
        }

        self.learning_dir.mkdir(parents=True, exist_ok=True)
        for folder in [*self.outbox_dirs.values(), *self.processed_dirs.values()]:
            folder.mkdir(parents=True, exist_ok=True)

        initialize_database(repo_root)
        self.lock = Lock()

    def _get_conn(self):
        return connect(self.repo_root)

    def count_lessons(self) -> int:
        with self.lock, self._get_conn() as conn:
            row = conn.execute("SELECT COUNT(*) AS count FROM lessons;").fetchone()
            return int(row["count"]) if row else 0

    def _extract_json_object(self, text: str) -> dict[str, Any] | None:
        raw = text.strip()
        if raw.startswith("```"):
            lines = raw.splitlines()
            if len(lines) >= 3:
                raw = "\n".join(lines[1:-1]).strip()
        try:
            parsed = json.loads(raw)
            if isinstance(parsed, dict):
                return parsed
        except json.JSONDecodeError:
            pass

        start = raw.find("{")
        end = raw.rfind("}")
        if start != -1 and end != -1 and end > start:
            try:
                parsed = json.loads(raw[start : end + 1])
                if isinstance(parsed, dict):
                    return parsed
            except json.JSONDecodeError:
                return None
        return None

    def _normalize_lane(self, lane: str | None) -> str:
        if lane is None:
            return "project"
        key = lane.strip().lower()
        return key if key in self.VALID_LANES else "project"

    def _normalize_origin_type(self, origin_type: str | None) -> str:
        key = (origin_type or ORIGIN_MANUAL_FEEDBACK).strip().lower()
        if key not in self.VALID_ORIGIN_TYPES:
            raise ValueError(
                f"Invalid origin_type '{origin_type}'. Valid values: {sorted(self.VALID_ORIGIN_TYPES)}"
            )
        return key

    def _origin_policy(self, origin_type: str | None) -> dict[str, Any]:
        key = self._normalize_origin_type(origin_type)
        return {
            "origin_type": key,
            "approvable": key in self.APPROVABLE_ORIGIN_TYPES,
            "allowed_in_guidance": key in self.GUIDANCE_ORIGIN_TYPES,
            "review_only": key in self.REVIEW_ONLY_ORIGIN_TYPES,
            "never_approve": key in self.NEVER_APPROVE_ORIGIN_TYPES,
        }

    def _heuristic_extract(self, feedback_text: str, lane_hint: str | None) -> dict[str, Any]:
        lines = [line.strip(" -*\t") for line in feedback_text.replace("\r\n", "\n").split("\n")]
        lines = [line for line in lines if line]
        summary = lines[0][:220] if lines else "Feedback ingested."
        lessons: list[dict[str, Any]] = []

        for line in lines[:6]:
            principle = line[:200]
            lessons.append(
                {
                    "principle": principle,
                    "trigger": "When similar requests occur again.",
                    "do": principle,
                    "avoid": "Ignoring this feedback in future decisions.",
                    "confidence": 0.55,
                    "lane": self._normalize_lane(lane_hint),
                    "tags": ["heuristic", "expert-feedback"],
                }
            )

        if not lessons:
            lessons.append(
                {
                    "principle": "Capture explicit user preferences and apply them consistently.",
                    "trigger": "When processing future user requests.",
                    "do": "Check prior feedback before deciding.",
                    "avoid": "Repeating previously rejected approaches.",
                    "confidence": 0.5,
                    "lane": self._normalize_lane(lane_hint),
                    "tags": ["fallback"],
                }
            )
        return {"summary": summary, "lessons": lessons}

    def _model_extract(self, feedback_text: str, lane_hint: str | None) -> dict[str, Any] | None:
        model = str(self.model_cfg.get("model", "")).strip()
        if not model:
            return None

        system_prompt = (
            "You are a learning parser for an AI orchestration system. "
            "Convert expert feedback into compact, reusable lessons that emulate human learning loops "
            "(reflection -> principle -> trigger -> behavior adjustment). "
            "Return strict JSON only with shape: "
            '{"summary":"...", "lessons":[{"principle":"...", "trigger":"...", "do":"...", "avoid":"...", "confidence":0.0, "lane":"research|ui|personal|project", "tags":["..."]}]}. '
            "Confidence must be between 0.0 and 1.0."
        )
        lane_value = self._normalize_lane(lane_hint)
        user_prompt = (
            f"Lane hint: {lane_value}\n\n"
            "Expert feedback to parse:\n"
            f"{feedback_text}\n\n"
            "Return only JSON."
        )
        try:
            response = self.client.chat(
                model=model,
                system_prompt=system_prompt,
                user_prompt=user_prompt,
                temperature=float(self.model_cfg.get("temperature", 0.1)),
                num_ctx=int(self.model_cfg.get("num_ctx", 16384)),
                think=bool(self.model_cfg.get("think", True)),
                timeout=int(self.model_cfg.get("timeout_sec", 300)),
            )
        except Exception:
            return None

        parsed = self._extract_json_object(response)
        if not parsed:
            return None
        lessons = parsed.get("lessons")
        if not isinstance(lessons, list) or not lessons:
            return None
        return parsed

    def _parse_feedback(self, feedback_text: str, lane_hint: str | None) -> dict[str, Any]:
        parsed = self._model_extract(feedback_text, lane_hint=lane_hint)
        if parsed is None:
            parsed = self._heuristic_extract(feedback_text, lane_hint=lane_hint)
        return parsed

    def _read_outbox_file(self, path: Path) -> str:
        suffix = path.suffix.lower()
        if suffix == ".json":
            try:
                data = json.loads(path.read_text(encoding="utf-8"))
            except json.JSONDecodeError:
                return path.read_text(encoding="utf-8", errors="ignore")
            if isinstance(data, dict):
                for key in ["response", "content", "final_answer", "analysis", "message", "text"]:
                    value = data.get(key)
                    if isinstance(value, str) and value.strip():
                        return value
                return json.dumps(data, indent=2, ensure_ascii=True)
            return json.dumps(data, ensure_ascii=True)
        return path.read_text(encoding="utf-8", errors="ignore")

    def _extract_outbox_response(self, raw_text: str) -> tuple[str, bool]:
        marker = "FINAL_RESPONSE:"
        body = raw_text.strip()
        if marker in raw_text:
            body = raw_text.split(marker, 1)[1].strip()
        is_incomplete = (not body) or (self.INCOMPLETE_TOKEN in body)
        return body, is_incomplete

    def _compose_guidance(self, item: dict[str, Any], principle: str) -> str:
        trigger = str(item.get("trigger", "When similar context appears.")).strip()
        do_text = str(item.get("do", "")).strip() or principle
        avoid_text = str(item.get("avoid", "")).strip() or "Repeating the prior mistake."
        return f"Trigger: {trigger}\nDo: {do_text}\nAvoid: {avoid_text}"

    def _guidance_is_duplicate(self, conn, guidance: str, lane: str) -> bool:
        """Return True if guidance is semantically similar (>0.90 cosine) to an existing active lesson."""
        try:
            client = OllamaClient()
            new_vec = client.embed("qwen3-embedding:4b", guidance[:2000])
        except Exception:
            return False
        try:
            rows = conn.execute(
                "SELECT guidance FROM lessons WHERE active = 1 AND lane IN (?, 'project') LIMIT 50;",
                (lane,),
            ).fetchall()
        except Exception:
            return False
        for row in rows:
            existing = str(row[0]).strip()
            if not existing:
                continue
            try:
                ev = client.embed("qwen3-embedding:4b", existing[:2000])
                dot = sum(x * y for x, y in zip(new_vec, ev))
                na = math.sqrt(sum(x * x for x in new_vec))
                nb = math.sqrt(sum(x * x for x in ev))
                if na > 0 and nb > 0 and (dot / (na * nb)) > 0.90:
                    return True
            except Exception:
                continue
        return False

    def _insert_lessons(
        self,
        conn,
        *,
        source: str,
        project: str,
        lane_hint: str | None,
        feedback_text: str,
        origin_type: str,
    ) -> list[str]:
        parsed = self._parse_feedback(feedback_text, lane_hint=lane_hint)
        summary_root = str(parsed.get("summary", "Feedback parsed")).strip() or "Feedback parsed"
        lessons = parsed.get("lessons") if isinstance(parsed.get("lessons"), list) else []
        inserted_ids: list[str] = []
        now = _now_iso()
        origin_key = self._normalize_origin_type(origin_type)

        for item in lessons[:10]:
            if not isinstance(item, dict):
                continue
            principle = str(item.get("principle", "")).strip()
            if not principle:
                continue
            try:
                conf = float(item.get("confidence", 0.6))
            except (TypeError, ValueError):
                conf = 0.6
            lane = self._normalize_lane(str(item.get("lane", lane_hint or "project")))
            lesson_id = uuid.uuid4().hex[:12]
            lesson_summary = principle[:220] if principle else summary_root[:220]
            guidance = self._compose_guidance(item, principle)
            if self._guidance_is_duplicate(conn, guidance, lane):
                continue
            conn.execute(
                """
                INSERT INTO lessons(
                    id,
                    lane,
                    project,
                    summary,
                    guidance,
                    origin_type,
                    source,
                    status,
                    confidence,
                    active,
                    approved_by,
                    created_at,
                    updated_at,
                    expires_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
                """,
                (
                    lesson_id,
                    lane,
                    project,
                    lesson_summary,
                    guidance,
                    origin_key,
                    source,
                    "candidate",
                    _clamp_score(conf),
                    0,
                    None,
                    now,
                    now,
                    _expires_iso(origin_key),
                ),
            )
            inserted_ids.append(lesson_id)

        return inserted_ids

    def ingest_feedback_text(
        self,
        *,
        feedback_text: str,
        source: str,
        lane_hint: str | None = None,
        project: str = "manual_feedback",
        source_file: str = "manual",
        origin_type: str = ORIGIN_MANUAL_FEEDBACK,
    ) -> dict[str, Any]:
        text = feedback_text.strip()
        if not text:
            return {
                "source": source,
                "processed_files": 0,
                "learned_lessons": 0,
                "lesson_ids": [],
                "message": "No feedback text provided.",
            }
        origin_key = self._normalize_origin_type(origin_type)
        with self.lock, self._get_conn() as conn:
            with transaction(conn, immediate=True):
                lesson_ids = self._insert_lessons(
                    conn,
                    source=source.strip().lower() or "manual",
                    project=project,
                    lane_hint=lane_hint,
                    feedback_text=text,
                    origin_type=origin_key,
                )
        return {
            "source": source,
            "origin_type": origin_key,
            "processed_files": 1,
            "learned_lessons": len(lesson_ids),
            "lesson_ids": lesson_ids,
            "source_file": source_file,
            "message": f"Ingested feedback text; staged {len(lesson_ids)} candidate lesson(s).",
        }

    def ingest_outbox(self, source: str, *, lane_hint: str | None = None, limit: int = 5) -> dict[str, Any]:
        source_key = source.strip().lower()
        if source_key not in self.VALID_SOURCES:
            raise ValueError("Invalid source. Use 'codex'.")
        limit = max(1, min(limit, 50))

        outbox_dir = self.outbox_dirs[source_key]
        processed_dir = self.processed_dirs[source_key]
        files = [p for p in outbox_dir.glob("*") if p.is_file() and p.name != ".gitkeep"]
        files.sort(key=lambda p: p.stat().st_mtime, reverse=True)
        files = files[:limit]

        if not files:
            return {
                "source": source_key,
                "origin_type": ORIGIN_OUTBOX_FEEDBACK,
                "processed_files": 0,
                "learned_lessons": 0,
                "lesson_ids": [],
                "message": f"No outbox files to ingest for {source_key}.",
            }

        inserted_ids: list[str] = []
        processed_count = 0
        skipped_incomplete = 0

        with self.lock, self._get_conn() as conn:
            with transaction(conn, immediate=True):
                for file_path in files:
                    raw_text = self._read_outbox_file(file_path)
                    text, is_incomplete = self._extract_outbox_response(raw_text)
                    if is_incomplete:
                        skipped_incomplete += 1
                        continue
                    lesson_ids = self._insert_lessons(
                        conn,
                        source=source_key,
                        project="handoff_feedback",
                        lane_hint=lane_hint,
                        feedback_text=text,
                        origin_type=ORIGIN_OUTBOX_FEEDBACK,
                    )
                    inserted_ids.extend(lesson_ids)
                    processed_count += 1

                    destination = processed_dir / file_path.name
                    if destination.exists():
                        stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                        destination = processed_dir / f"{file_path.stem}_{stamp}{file_path.suffix}"
                    shutil.move(str(file_path), str(destination))

        return {
            "source": source_key,
            "origin_type": ORIGIN_OUTBOX_FEEDBACK,
            "processed_files": processed_count,
            "skipped_incomplete": skipped_incomplete,
            "learned_lessons": len(inserted_ids),
            "lesson_ids": inserted_ids,
            "message": (
                f"Ingested {processed_count} outbox file(s) from {source_key}; "
                f"skipped {skipped_incomplete} incomplete placeholder(s); "
                f"staged {len(inserted_ids)} candidate lesson(s)."
            ),
        }

    def ingest_outbox_thread(self, source: str, *, request_id: str, lane_hint: str | None = None) -> dict[str, Any]:
        source_key = source.strip().lower()
        if source_key not in self.VALID_SOURCES:
            raise ValueError("Invalid source. Use 'codex'.")
        thread_id = request_id.strip()
        if not thread_id:
            raise ValueError("Thread id is required.")

        outbox_dir = self.outbox_dirs[source_key]
        processed_dir = self.processed_dirs[source_key]
        candidates = sorted(
            [p for p in outbox_dir.glob(f"{thread_id}.*") if p.is_file()],
            key=lambda p: p.stat().st_mtime,
            reverse=True,
        )
        if not candidates:
            return {
                "source": source_key,
                "origin_type": ORIGIN_OUTBOX_FEEDBACK,
                "thread_id": thread_id,
                "processed_files": 0,
                "skipped_incomplete": 0,
                "learned_lessons": 0,
                "lesson_ids": [],
                "message": f"No outbox file found for thread {thread_id}.",
            }

        file_path = candidates[0]
        inserted_ids: list[str] = []
        processed_count = 0
        skipped_incomplete = 0

        with self.lock, self._get_conn() as conn:
            with transaction(conn, immediate=True):
                raw_text = self._read_outbox_file(file_path)
                text, is_incomplete = self._extract_outbox_response(raw_text)
                if is_incomplete:
                    skipped_incomplete = 1
                else:
                    lesson_ids = self._insert_lessons(
                        conn,
                        source=source_key,
                        project="handoff_feedback",
                        lane_hint=lane_hint,
                        feedback_text=text,
                        origin_type=ORIGIN_OUTBOX_FEEDBACK,
                    )
                    inserted_ids.extend(lesson_ids)
                    processed_count = 1

                    destination = processed_dir / file_path.name
                    if destination.exists():
                        stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                        destination = processed_dir / f"{file_path.stem}_{stamp}{file_path.suffix}"
                    shutil.move(str(file_path), str(destination))

        return {
            "source": source_key,
            "origin_type": ORIGIN_OUTBOX_FEEDBACK,
            "thread_id": thread_id,
            "processed_files": processed_count,
            "skipped_incomplete": skipped_incomplete,
            "learned_lessons": len(inserted_ids),
            "lesson_ids": inserted_ids,
            "message": (
                f"Ingested {processed_count} outbox file(s) for {thread_id} from {source_key}; "
                f"skipped {skipped_incomplete} incomplete placeholder(s); "
                f"staged {len(inserted_ids)} candidate lesson(s)."
            ),
        }

    def outbox_text(self, source: str | None = None, limit: int = 20) -> str:
        limit = max(1, min(limit, 100))
        sources = [source.strip().lower()] if source else ["codex"]
        lines: list[str] = []
        for key in sources:
            if key not in self.VALID_SOURCES:
                return "Invalid source. Use 'codex'."
            rows = [p for p in self.outbox_dirs[key].glob("*") if p.is_file() and p.name != ".gitkeep"]
            rows.sort(key=lambda p: p.stat().st_mtime, reverse=True)
            lines.append(f"{key} outbox ({len(rows)}):")
            if not rows:
                lines.append("- empty")
                continue
            for path in rows[:limit]:
                lines.append(f"- {path.name}")
        return "\n".join(lines)

    def list_lessons(
        self,
        lane: str | None = None,
        limit: int = 20,
        sort_by: str = "confidence",
        status: str | None = None,
        include_inactive: bool = True,
        origin_type: str | None = None,
    ) -> list[dict[str, Any]]:
        lane_key = self._normalize_lane(lane) if lane else None
        limit = max(1, min(limit, 100))
        mode = str(sort_by or "confidence").strip().lower()
        query = [
            "SELECT id, lane, project, summary, guidance, origin_type, source, status, confidence, active, approved_by, created_at, updated_at, expires_at",
            "FROM lessons",
            "WHERE 1=1",
        ]
        params: list[Any] = []

        if lane_key:
            query.append("AND lane = ?")
            params.append(lane_key)
        if status and status.strip().lower() in self.VALID_STATUSES:
            query.append("AND status = ?")
            params.append(status.strip().lower())
        if origin_type:
            query.append("AND origin_type = ?")
            params.append(self._normalize_origin_type(origin_type))
        if not include_inactive:
            query.append("AND active = 1")
        if mode == "newest":
            query.append("ORDER BY updated_at DESC, confidence DESC")
        else:
            query.append("ORDER BY confidence DESC, updated_at DESC")
        query.append("LIMIT ?")
        params.append(limit)

        with self.lock, self._get_conn() as conn:
            rows = conn.execute(" ".join(query), params).fetchall()
        return [row_to_dict(row) or {} for row in rows]

    def approve_lesson(self, lesson_id: str, approved_by: str = "owner") -> dict[str, Any] | None:
        lesson_id = lesson_id.strip()
        if not lesson_id:
            return None
        now = _now_iso()
        with self.lock, self._get_conn() as conn:
            row = conn.execute(
                "SELECT id, lane, project, summary, guidance, origin_type, source, status, confidence, active, approved_by, created_at, updated_at, expires_at FROM lessons WHERE id = ?;",
                (lesson_id,),
            ).fetchone()
            if row is None:
                return None
            current = row_to_dict(row) or {}
            policy = self._origin_policy(current.get("origin_type"))
            if policy["never_approve"] or not policy["approvable"]:
                current["policy_blocked"] = True
                current["policy_message"] = (
                    f"Lessons from origin '{policy['origin_type']}' cannot become approved learning. "
                    "Rewrite or restate the lesson as manual feedback if you want it to affect prompts."
                )
                return current
            with transaction(conn, immediate=True):
                conn.execute(
                    """
                    UPDATE lessons
                    SET status = 'approved', active = 1, approved_by = ?, updated_at = ?
                    WHERE id = ?;
                    """,
                    (approved_by.strip() or "owner", now, lesson_id),
                )
                row = conn.execute(
                    "SELECT id, lane, project, summary, guidance, origin_type, source, status, confidence, active, approved_by, created_at, updated_at, expires_at FROM lessons WHERE id = ?;",
                    (lesson_id,),
                ).fetchone()
        approved = row_to_dict(row) or {}
        approved["policy_blocked"] = False
        approved["policy_message"] = "Lesson approved for prompt guidance."
        return approved

    def promote_lesson(self, lesson_id: str, approved_by: str = "owner") -> dict[str, Any] | None:
        return self.approve_lesson(lesson_id=lesson_id, approved_by=approved_by)

    def reject_lesson(self, lesson_id: str, rejected_by: str = "owner") -> dict[str, Any] | None:
        lesson_id = lesson_id.strip()
        if not lesson_id:
            return None
        now = _now_iso()
        with self.lock, self._get_conn() as conn:
            with transaction(conn, immediate=True):
                conn.execute(
                    """
                    UPDATE lessons
                    SET status = 'rejected', active = 0, approved_by = ?, updated_at = ?
                    WHERE id = ?;
                    """,
                    (rejected_by.strip() or "owner", now, lesson_id),
                )
                row = conn.execute(
                    "SELECT id, lane, project, summary, guidance, origin_type, source, status, confidence, active, approved_by, created_at, updated_at, expires_at FROM lessons WHERE id = ?;",
                    (lesson_id,),
                ).fetchone()
        return row_to_dict(row)

    def expire_lesson(self, lesson_id: str) -> dict[str, Any] | None:
        lesson_id = lesson_id.strip()
        if not lesson_id:
            return None
        now = _now_iso()
        with self.lock, self._get_conn() as conn:
            with transaction(conn, immediate=True):
                conn.execute(
                    """
                    UPDATE lessons
                    SET status = 'expired', active = 0, updated_at = ?, expires_at = COALESCE(expires_at, ?)
                    WHERE id = ?;
                    """,
                    (now, now, lesson_id),
                )
                row = conn.execute(
                    "SELECT id, lane, project, summary, guidance, origin_type, source, status, confidence, active, approved_by, created_at, updated_at, expires_at FROM lessons WHERE id = ?;",
                    (lesson_id,),
                ).fetchone()
        return row_to_dict(row)

    def guidance_for_lane(self, lane: str, limit: int = 5) -> str:
        lane_key = self._normalize_lane(lane)
        limit = max(1, min(limit, 50))
        now = _now_iso()
        with self.lock, self._get_conn() as conn:
            rows = conn.execute(
                """
                SELECT id, lane, summary, guidance, confidence, origin_type
                FROM lessons
                WHERE active = 1
                  AND status = 'approved'
                  AND origin_type IN (?, ?, ?)
                  AND lane IN (?, 'project')
                  AND (expires_at IS NULL OR expires_at > ?)
                ORDER BY confidence DESC, updated_at DESC
                LIMIT ?;
                """,
                (ORIGIN_MANUAL_FEEDBACK, ORIGIN_OUTBOX_FEEDBACK, ORIGIN_REFLECTION, lane_key, now, limit),
            ).fetchall()

        if rows:
            lines = ["Learned guidance from approved feedback:"]
            for row in rows:
                lines.append(f"- [{row['id']}] ({row['origin_type']}) {row['summary']}\n  {row['guidance']}")
            return "\n".join(lines)

        # Fallback path: if no approved lessons exist, allow high-confidence
        # candidate lessons from approvable origins so guidance does not regress
        # to generic behavior. These remain visible as candidate-sourced.
        min_conf = float(self.GUIDANCE_CANDIDATE_FALLBACK_MIN_CONFIDENCE)
        with self.lock, self._get_conn() as conn:
            candidate_rows = conn.execute(
                """
                SELECT id, lane, summary, guidance, confidence, origin_type
                FROM lessons
                WHERE status = 'candidate'
                  AND origin_type IN (?, ?, ?)
                  AND lane IN (?, 'project')
                  AND confidence >= ?
                  AND (expires_at IS NULL OR expires_at > ?)
                ORDER BY confidence DESC, updated_at DESC
                LIMIT ?;
                """,
                (
                    ORIGIN_MANUAL_FEEDBACK,
                    ORIGIN_OUTBOX_FEEDBACK,
                    ORIGIN_REFLECTION,
                    lane_key,
                    min_conf,
                    now,
                    limit,
                ),
            ).fetchall()

        if not candidate_rows:
            return ""

        lines = ["Learned guidance from high-confidence candidate feedback:"]
        for row in candidate_rows:
            lines.append(
                f"- [{row['id']}] ({row['origin_type']}) {row['summary']}\n  {row['guidance']}"
            )
        return "\n".join(lines)

    def lessons_text(
        self,
        lane: str | None = None,
        limit: int = 10,
        status: str | None = None,
        origin_type: str | None = None,
    ) -> str:
        rows = self.list_lessons(lane=lane, limit=limit, status=status, origin_type=origin_type)
        if not rows:
            return "No learned lessons yet."
        header = f"Learned lessons ({len(rows)} shown):"
        lines = [header]
        for row in rows:
            policy = self._origin_policy(row.get('origin_type'))
            trust_bits = []
            if policy['review_only']:
                trust_bits.append('review-only')
            if policy['never_approve']:
                trust_bits.append('never-approve')
            if policy['allowed_in_guidance']:
                trust_bits.append('guidance-ok')
            policy_note = ','.join(trust_bits) if trust_bits else 'standard'
            lines.append(
                f"- {row.get('id','')} | lane={row.get('lane','')} | origin={row.get('origin_type','')} | status={row.get('status','')} | "
                f"active={int(bool(row.get('active', 0)))} | confidence={float(row.get('confidence', 0.0)):.2f} | "
                f"policy={policy_note} | summary={row.get('summary','')}"
            )
        return "\n".join(lines)

    def reinforce(self, lesson_id: str, direction: str, note: str = "") -> dict[str, Any] | None:
        direction_key = direction.strip().lower()
        if direction_key not in {"up", "down"}:
            raise ValueError("Direction must be 'up' or 'down'.")
        lesson_id = lesson_id.strip()
        if not lesson_id:
            return None
        now = _now_iso()
        with self.lock, self._get_conn() as conn:
            row = conn.execute(
                "SELECT id, confidence, status, active FROM lessons WHERE id = ?;",
                (lesson_id,),
            ).fetchone()
            if row is None:
                return None
            confidence = float(row["confidence"])
            if direction_key == "up":
                confidence += 0.08
            else:
                confidence -= 0.12
            confidence = _clamp_score(confidence)
            new_status = str(row["status"])
            new_active = int(row["active"])
            if direction_key == "down" and confidence <= 0.05:
                new_status = "expired"
                new_active = 0
            with transaction(conn, immediate=True):
                conn.execute(
                    "UPDATE lessons SET confidence = ?, status = ?, active = ?, updated_at = ? WHERE id = ?;",
                    (confidence, new_status, new_active, now, lesson_id),
                )
                updated = conn.execute(
                    "SELECT id, lane, project, summary, guidance, origin_type, source, status, confidence, active, approved_by, created_at, updated_at, expires_at FROM lessons WHERE id = ?;",
                    (lesson_id,),
                ).fetchone()
        return row_to_dict(updated)


__all__ = [
    "FeedbackLearningEngine",
    "ORIGIN_MANUAL_FEEDBACK",
    "ORIGIN_OUTBOX_FEEDBACK",
    "ORIGIN_REFLECTION",
    "ORIGIN_CLOUD_CRITIQUE",
    "VALID_ORIGIN_TYPES",
    "APPROVABLE_ORIGIN_TYPES",
    "GUIDANCE_ORIGIN_TYPES",
    "REVIEW_ONLY_ORIGIN_TYPES",
    "NEVER_APPROVE_ORIGIN_TYPES",
]
