from __future__ import annotations

import json
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path
from threading import Lock
import threading
from typing import Any

from shared_tools.feedback_learning import (
    FeedbackLearningEngine,
    ORIGIN_REFLECTION,
)
from shared_tools.ollama_client import OllamaClient


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


_LANE_REFLECTION_CONTEXT: dict[str, str] = {
    "research": (
        "Focus on evidence quality, source diversity, and claim precision. "
        "Ask whether findings were backed by empirical sources or relied on inference/speculation."
    ),
    "personal": (
        "Focus on intent matching, task completeness, and household priority accuracy. "
        "Ask whether the response addressed the real underlying need."
    ),
    "ui": (
        "Focus on output formatting, code correctness, and user-visible quality. "
        "Ask whether the generated artifact matches the expected style and is immediately usable."
    ),
    "project": (
        "Focus on scope accuracy, deliverable clarity, and context coverage. "
        "Ask whether the response stayed on-scope and produced something actionable."
    ),
}

_LANE_FALLBACK_QUESTIONS: dict[str, str] = {
    "research": (
        "Which part of this research summary was least supported by evidence, "
        "and what source type would strengthen it?"
    ),
    "personal": (
        "Did this response match your actual intent? "
        "If not, what would a better interpretation have been?"
    ),
    "ui": (
        "Does the generated output match the style and format you expected? "
        "What specific change would make it immediately usable?"
    ),
    "project": (
        "Was the scope of this response appropriate — too narrow, too broad, or just right? "
        "What was the most important thing that was missed?"
    ),
}


class SelfReflectionEngine:
    def __init__(
        self,
        repo_root: Path,
        *,
        client: OllamaClient,
        learning_engine: FeedbackLearningEngine,
        model_cfg: dict[str, Any] | None = None,
    ) -> None:
        self.repo_root = repo_root
        self.client = client
        self.learning_engine = learning_engine
        self.model_cfg = model_cfg or {}

        self.path = repo_root / "Runtime" / "learning" / "reflections.json"
        self.path.parent.mkdir(parents=True, exist_ok=True)
        if not self.path.exists():
            self.path.write_text("[]", encoding="utf-8")

        self.max_open_before_gate = int(self.model_cfg.get("reflection_gate_open_limit", 3))
        self.lock = Lock()

    def _load(self) -> list[dict[str, Any]]:
        try:
            data = json.loads(self.path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            return []
        return data if isinstance(data, list) else []

    def _save(self, rows: list[dict[str, Any]]) -> None:
        self.path.write_text(json.dumps(rows, indent=2, ensure_ascii=True), encoding="utf-8")

    def count_open(self) -> int:
        with self.lock:
            rows = self._load()
        return len([row for row in rows if str(row.get("status", "")).lower() == "open"])

    def should_gate(self) -> bool:
        return self.count_open() >= self.max_open_before_gate

    def gate_text(self) -> str:
        return (
            "Reflection gate is active because there are multiple open self-reflection questions. "
            "Answer one using /reflect-open then /reflect-answer <id> <answer>."
        )

    def _extract_json(self, text: str) -> dict[str, Any] | None:
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

    def _fallback_reflection(
        self,
        *,
        project: str,
        lane: str,
        user_request: str,
        orchestrator_reply: str,
    ) -> dict[str, Any]:
        summary = "Cycle completed. Reflection generated with fallback parser."
        improvements = [
            "State explicit assumptions before giving final recommendations.",
            "Capture missing constraints early and ask clarifying questions.",
            "Tie each recommendation to an actionable next step with owner and timeline.",
        ]
        question = _LANE_FALLBACK_QUESTIONS.get(
            lane.strip().lower(),
            f"What is one concrete thing that would improve the next '{lane}' response?",
        )
        return {
            "summary": summary,
            "what_went_well": ["Response produced and artifacts written for review."],
            "what_to_improve": improvements,
            "next_experiment": "Apply one improvement in the next similar task and measure quality.",
            "question_for_user": question,
            "lane": lane,
            "project": project,
            "user_request": user_request[:400],
            "orchestrator_reply": orchestrator_reply[:400],
        }

    def _model_reflection(
        self,
        *,
        project: str,
        lane: str,
        user_request: str,
        orchestrator_reply: str,
        worker_result: dict[str, Any] | None,
    ) -> dict[str, Any] | None:
        model = str(self.model_cfg.get("model", "")).strip()
        if not model:
            return None

        lane_context = _LANE_REFLECTION_CONTEXT.get(lane.strip().lower(), "")
        lane_question_hint = _LANE_FALLBACK_QUESTIONS.get(
            lane.strip().lower(),
            f"What is one concrete thing that would improve the next '{lane}' response?",
        )
        system_prompt = (
            "You are a self-reflection module for an AI orchestrator. "
            "Perform reflective analysis in a human-learning style: "
            "outcome review, assumptions check, error risk, and behavior adjustment. "
            f"Lane context: {lane_context} "
            "The question_for_user must be lane-specific, concrete, and answerable in 1-2 sentences. "
            "Avoid generic questions like 'What went well?' — ask about a specific quality dimension. "
            f"Example question style: '{lane_question_hint}' "
            "Return strict JSON only with keys: "
            '{"summary":"...", "what_went_well":["..."], "what_to_improve":["..."], '
            '"next_experiment":"...", "question_for_user":"..."}'
        )
        user_prompt = (
            f"Project: {project}\nLane: {lane}\n\n"
            f"User request:\n{user_request}\n\n"
            f"Orchestrator reply:\n{orchestrator_reply}\n\n"
            f"Worker result object:\n{worker_result or {}}\n\n"
            "Generate one concrete, lane-specific question_for_user that identifies a specific "
            "improvement in the orchestrator's handling of this type of task."
        )
        try:
            raw = self.client.chat(
                model=model,
                system_prompt=system_prompt,
                user_prompt=user_prompt,
                temperature=float(self.model_cfg.get("reflection_temperature", 0.2)),
                num_ctx=int(self.model_cfg.get("reflection_num_ctx", 16384)),
                think=bool(self.model_cfg.get("reflection_think", True)),
                timeout=int(self.model_cfg.get("reflection_timeout_sec", 300)),
            )
        except Exception:
            return None

        parsed = self._extract_json(raw)
        if not parsed:
            return None
        if not isinstance(parsed.get("what_to_improve"), list):
            return None
        return parsed

    def create_cycle(
        self,
        *,
        project: str,
        lane: str,
        user_request: str,
        orchestrator_reply: str,
        worker_result: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        parsed = self._model_reflection(
            project=project,
            lane=lane,
            user_request=user_request,
            orchestrator_reply=orchestrator_reply,
            worker_result=worker_result,
        )
        if parsed is None:
            parsed = self._fallback_reflection(
                project=project,
                lane=lane,
                user_request=user_request,
                orchestrator_reply=orchestrator_reply,
            )

        cycle_id = uuid.uuid4().hex[:10]
        improvements = [str(x).strip() for x in parsed.get("what_to_improve", []) if str(x).strip()][:5]
        question = str(parsed.get("question_for_user", "")).strip() or (
            f"What should we improve next for lane '{lane}'?"
        )

        reflection = {
            "id": cycle_id,
            "status": "open",
            "project": project,
            "lane": lane,
            "summary": str(parsed.get("summary", "")).strip(),
            "what_went_well": [str(x).strip() for x in parsed.get("what_went_well", []) if str(x).strip()][:5],
            "what_to_improve": improvements,
            "next_experiment": str(parsed.get("next_experiment", "")).strip(),
            "question_for_user": question,
            "created_at": _now_iso(),
            "updated_at": _now_iso(),
            "user_request": user_request[:1000],
            "orchestrator_reply": orchestrator_reply[:1000],
            "worker_result": worker_result or {},
            "auto_lesson_ids": [],
            "answer": "",
            "answer_lesson_ids": [],
        }

        auto_feedback = "\n".join(
            [
                f"Reflection summary: {reflection['summary']}",
                "Improvements:",
                *[f"- {line}" for line in improvements],
                f"Next experiment: {reflection['next_experiment']}",
            ]
        ).strip()

        if auto_feedback:
            auto = self.learning_engine.ingest_feedback_text(
                feedback_text=auto_feedback,
                source="self_reflection_auto",
                lane_hint=lane,
                project=project,
                source_file=f"reflection:auto:{cycle_id}",
                origin_type=ORIGIN_REFLECTION,
            )
            reflection["auto_lesson_ids"] = auto.get("lesson_ids", [])

        with self.lock:
            rows = self._load()
            rows.append(reflection)
            self._save(rows)
        return reflection

    def list_open(self, limit: int = 10) -> list[dict[str, Any]]:
        limit = max(1, min(limit, 100))
        with self.lock:
            rows = self._load()
        open_rows = [row for row in rows if str(row.get("status", "")).lower() == "open"]
        open_rows.sort(key=lambda row: str(row.get("created_at", "")), reverse=True)
        return open_rows[:limit]

    def list_history(self, limit: int = 50) -> list[dict[str, Any]]:
        limit = max(1, min(limit, 300))
        with self.lock:
            rows = self._load()
        rows.sort(key=lambda row: str(row.get("created_at", "")), reverse=True)
        return rows[:limit]

    def open_text(self, limit: int = 10) -> str:
        rows = self.list_open(limit=limit)
        if not rows:
            return "No open self-reflection questions."
        lines = [f"Open self-reflection questions ({len(rows)} shown):"]
        for row in rows:
            lines.append(
                f"- {row.get('id','')} | lane={row.get('lane','')} | "
                f"question={row.get('question_for_user','')}"
            )
        return "\n".join(lines)

    def history_text(self, limit: int = 10) -> str:
        limit = max(1, min(limit, 100))
        with self.lock:
            rows = self._load()
        rows.sort(key=lambda row: str(row.get("created_at", "")), reverse=True)
        if not rows:
            return "No reflection cycles yet."
        lines = [f"Reflection history ({min(limit, len(rows))} shown):"]
        for row in rows[:limit]:
            lines.append(
                f"- {row.get('id','')} | status={row.get('status','')} | lane={row.get('lane','')} | "
                f"summary={row.get('summary','')}"
            )
        return "\n".join(lines)

    def answer(self, cycle_id: str, answer_text: str) -> dict[str, Any] | None:
        answer = answer_text.strip()
        if not answer:
            raise ValueError("Answer text cannot be empty.")

        with self.lock:
            rows = self._load()
            idx = -1
            for i, row in enumerate(rows):
                if str(row.get("id", "")) == cycle_id:
                    idx = i
                    break
            if idx == -1:
                return None
            cycle = rows[idx]
            if str(cycle.get("status", "")).lower() != "open":
                return None

            cycle["status"] = "closed"
            cycle["answer"] = answer
            cycle["answered_at"] = _now_iso()
            cycle["updated_at"] = _now_iso()
            cycle["learning_status"] = "queued"
            cycle["learning_error"] = ""
            cycle["answer_lesson_ids"] = []
            rows[idx] = cycle
            self._save(rows)

        lesson_payload = "\n".join(
            [
                f"Reflection question: {cycle.get('question_for_user','')}",
                f"User answer: {answer}",
                "Reflection improvements:",
                *[f"- {line}" for line in cycle.get("what_to_improve", [])],
                f"Next experiment: {cycle.get('next_experiment','')}",
            ]
        ).strip()
        self._ingest_answer_lessons_async(cycle_id=cycle_id, cycle=cycle, lesson_payload=lesson_payload)
        return cycle

    def _ingest_answer_lessons_async(self, *, cycle_id: str, cycle: dict[str, Any], lesson_payload: str) -> None:
        lane = str(cycle.get("lane", "project"))
        project = str(cycle.get("project", "reflection_feedback"))

        def _worker() -> None:
            self._set_learning_status(cycle_id, status="running", error="", lesson_ids=[])
            try:
                learned = self.learning_engine.ingest_feedback_text(
                    feedback_text=lesson_payload,
                    source="self_reflection_user",
                    lane_hint=lane,
                    project=project,
                    source_file=f"reflection:user:{cycle_id}",
                    origin_type=ORIGIN_REFLECTION,
                )
                lesson_ids = learned.get("lesson_ids", []) if isinstance(learned, dict) else []
                self._set_learning_status(cycle_id, status="completed", error="", lesson_ids=lesson_ids)
            except Exception as exc:
                self._set_learning_status(
                    cycle_id,
                    status="failed",
                    error=str(exc).strip()[:500],
                    lesson_ids=[],
                )

        threading.Thread(
            target=_worker,
            daemon=True,
            name=f"reflection-learn-{cycle_id[:8]}",
        ).start()

    def _set_learning_status(
        self,
        cycle_id: str,
        *,
        status: str,
        error: str,
        lesson_ids: list[str],
    ) -> None:
        with self.lock:
            rows = self._load()
            for i, row in enumerate(rows):
                if str(row.get("id", "")) != cycle_id:
                    continue
                row["learning_status"] = str(status).strip()
                row["learning_error"] = str(error or "").strip()
                row["answer_lesson_ids"] = list(lesson_ids or [])
                row["updated_at"] = _now_iso()
                rows[i] = row
                break
            self._save(rows)

    def auto_answer(self, cycle_id: str) -> dict[str, Any] | None:
        """Auto-answer an open reflection cycle using the model.

        Used to close stale cycles so their lessons flow through to the learning store.
        Returns the closed cycle dict, or None if the cycle was not found / not open.
        """
        cycle = self.get_cycle(cycle_id)
        if cycle is None or str(cycle.get("status", "")).lower() != "open":
            return None

        improvements = cycle.get("what_to_improve", [])
        fallback_answer = (
            "Auto-answer: " + "; ".join(str(x) for x in improvements[:3])
            if improvements
            else "No specific improvements identified for this cycle."
        )

        model = str(self.model_cfg.get("model", "")).strip()
        if not model:
            return self.answer(cycle_id=cycle_id, answer_text=fallback_answer)

        system_prompt = (
            "You are an auto-answering module for a self-reflection system. "
            "Given a reflection question and context from a completed AI response, "
            "provide a concrete 1-2 sentence answer that is useful as a lesson for future runs. "
            "Be specific and actionable. Do not hedge or waffle. Return plain text only — no markdown."
        )
        lane = str(cycle.get("lane", "project"))
        user_prompt = (
            f"Lane: {lane}\n"
            f"Reflection question: {cycle.get('question_for_user', '')}\n\n"
            f"What went well: {'; '.join(str(x) for x in cycle.get('what_went_well', []))}\n"
            f"What to improve: {'; '.join(str(x) for x in cycle.get('what_to_improve', []))}\n"
            f"Next experiment: {cycle.get('next_experiment', '')}\n\n"
            f"Original user request: {str(cycle.get('user_request', ''))[:300]}\n\n"
            "Provide a concrete, actionable 1-2 sentence answer to the reflection question."
        )
        try:
            raw = self.client.chat(
                model=model,
                system_prompt=system_prompt,
                user_prompt=user_prompt,
                temperature=0.3,
                num_ctx=int(self.model_cfg.get("reflection_num_ctx", 8192)),
                think=False,
                timeout=int(self.model_cfg.get("reflection_timeout_sec", 120)),
            )
            answer_text = str(raw or "").strip()
        except Exception:
            answer_text = ""

        return self.answer(cycle_id=cycle_id, answer_text=answer_text or fallback_answer)

    def auto_answer_stale_cycles(self, max_age_hours: float = 24.0) -> list[str]:
        """Auto-answer open reflection cycles older than *max_age_hours*.

        Calling this closes stale open cycles and pushes their insights through the lesson
        pipeline so guidance actually gets populated. Returns list of closed cycle IDs.
        """
        cutoff = datetime.now(timezone.utc) - timedelta(hours=max(0.0, float(max_age_hours)))
        with self.lock:
            rows = self._load()
        stale_ids: list[str] = []
        for row in rows:
            if str(row.get("status", "")).lower() != "open":
                continue
            created_raw = str(row.get("created_at", "")).strip()
            try:
                created = datetime.fromisoformat(created_raw.replace("Z", "+00:00"))
                if created.tzinfo is None:
                    created = created.replace(tzinfo=timezone.utc)
            except ValueError:
                continue
            if created <= cutoff:
                stale_ids.append(str(row.get("id", "")))
        closed_ids: list[str] = []
        for cycle_id in stale_ids:
            result = self.auto_answer(cycle_id)
            if result is not None:
                closed_ids.append(cycle_id)
        return closed_ids

    def get_cycle(self, cycle_id: str) -> dict[str, Any] | None:
        with self.lock:
            rows = self._load()
        for row in rows:
            if str(row.get("id", "")) == cycle_id:
                return row
        return None

    def ignore(self, cycle_id: str, reason: str = "") -> dict[str, Any] | None:
        with self.lock:
            rows = self._load()
            idx = -1
            for i, row in enumerate(rows):
                if str(row.get("id", "")) == cycle_id:
                    idx = i
                    break
            if idx == -1:
                return None
            cycle = rows[idx]
            if str(cycle.get("status", "")).lower() != "open":
                return None

            cycle["status"] = "ignored"
            cycle["ignored_reason"] = reason.strip()
            cycle["ignored_at"] = _now_iso()
            cycle["updated_at"] = _now_iso()
            rows[idx] = cycle
            self._save(rows)
            return cycle

    def route_to_external(self, cycle_id: str, target: str, note: str = "") -> dict[str, Any] | None:
        with self.lock:
            rows = self._load()
            idx = -1
            for i, row in enumerate(rows):
                if str(row.get("id", "")) == cycle_id:
                    idx = i
                    break
            if idx == -1:
                return None
            cycle = rows[idx]
            if str(cycle.get("status", "")).lower() != "open":
                return None

            cycle["status"] = f"routed_{target.strip().lower()}"
            cycle["routed_target"] = target.strip().lower()
            cycle["routed_note"] = note.strip()
            cycle["routed_at"] = _now_iso()
            cycle["updated_at"] = _now_iso()
            rows[idx] = cycle
            self._save(rows)
            return cycle
