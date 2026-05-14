from __future__ import annotations

import logging
import re
import threading
import uuid
import json
from difflib import SequenceMatcher
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from infra.persistence.repositories import WatchtowerRepository
from shared_tools.topic_engine import VALID_TOPIC_TYPES
from watchtower import WatchtowerScout


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _now_utc() -> datetime:
    return datetime.now(timezone.utc)


def _slug(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", text.strip().lower()).strip("-")[:40]


def _normalize_heading(text: str) -> str:
    low = str(text or "").strip().lower()
    return re.sub(r"[^a-z0-9]+", " ", low).strip()


def _clean_text(text: str) -> str:
    raw = str(text or "").replace("\r\n", "\n").strip()
    if not raw:
        return ""
    return re.sub(r"\s+", " ", raw).strip()


def _strip_markdown_noise(text: str) -> str:
    value = str(text or "")
    value = re.sub(r"`{1,3}", "", value)
    value = value.replace("**", "").replace("__", "").replace("*", "")
    value = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", value)
    return _clean_text(value)


def _split_sentences(text: str, limit: int = 2) -> list[str]:
    cleaned = _strip_markdown_noise(text)
    if not cleaned:
        return []
    parts = [p.strip() for p in re.split(r"(?<=[.!?])\s+", cleaned) if p.strip()]
    return parts[: max(1, int(limit or 1))]


def _first_sentence(text: str) -> str:
    rows = _split_sentences(text, limit=1)
    return rows[0] if rows else ""


def _extract_section(markdown: str, heading_aliases: list[str]) -> str:
    text = str(markdown or "")
    if not text.strip():
        return ""
    matches = list(re.finditer(r"^\s{0,3}#{1,6}\s*(.+?)\s*$", text, flags=re.MULTILINE))
    if not matches:
        return ""

    targets = [_normalize_heading(name) for name in heading_aliases if str(name or "").strip()]
    for idx, match in enumerate(matches):
        heading = _normalize_heading(match.group(1))
        if not heading:
            continue
        if not any(target in heading for target in targets):
            continue
        start = match.end()
        end = matches[idx + 1].start() if idx + 1 < len(matches) else len(text)
        return text[start:end].strip()
    return ""


def _extract_bullets(section_text: str, limit: int = 4) -> list[str]:
    out: list[str] = []
    for line in str(section_text or "").splitlines():
        raw = str(line or "").strip()
        if not raw:
            continue
        raw = re.sub(r"^[\-\*\u2022]\s+", "", raw)
        raw = re.sub(r"^\d+[.)]\s+", "", raw)
        cleaned = _strip_markdown_noise(raw)
        if not cleaned:
            continue
        out.append(cleaned)
        if len(out) >= max(1, int(limit or 1)):
            break
    return out


def _confidence_from_text(markdown: str) -> tuple[str, str]:
    text = str(markdown or "")
    if not text:
        return "", "unknown"
    match = re.search(r"evidence confidence\s*:\s*([^\n\r]+)", text, flags=re.IGNORECASE)
    raw = _clean_text(match.group(1)) if match else ""
    low = raw.lower()
    if "high" in low:
        return raw, "high"
    if "medium" in low:
        return raw, "medium"
    if "low" in low:
        return raw, "low"
    if re.search(r"\b[45]\s*/\s*5\b", low):
        return raw, "high"
    if re.search(r"\b3\s*/\s*5\b", low):
        return raw, "medium"
    if re.search(r"\b[12]\s*/\s*5\b", low):
        return raw, "low"
    return raw, "unknown"


def _source_count(markdown: str) -> int:
    text = str(markdown or "")
    if not text:
        return 0
    return len(re.findall(r"https?://", text, flags=re.IGNORECASE))


def _text_similarity(left: str, right: str) -> float:
    a = _strip_markdown_noise(left)
    b = _strip_markdown_noise(right)
    if not a or not b:
        return 0.0
    return float(SequenceMatcher(None, a[:4000], b[:4000]).ratio())


def _build_briefing_digest(topic: str, markdown: str) -> dict[str, Any]:
    text = str(markdown or "")
    if not text.strip():
        fallback = str(topic or "Watchtower research card").strip() or "Watchtower research card"
        return {
            "headline": fallback,
            "summary": "",
            "key_points": [],
            "risks": [],
            "next_steps": [],
            "confidence_raw": "",
            "confidence_label": "unknown",
            "source_count": 0,
            "signal_score": 0,
            "quality_flags": ["empty_briefing"],
        }

    title = _clean_text(
        re.sub(r"^\s*#{1,6}\s*", "", text.splitlines()[0] if text.splitlines() else "", flags=re.IGNORECASE)
    )
    summary_body = _extract_section(text, ["executive summary", "summary", "overview"])
    findings_body = _extract_section(text, ["key findings", "findings", "takeaways"])
    risks_body = _extract_section(text, ["uncertainties & risks", "risks", "uncertainties"])
    next_steps_body = _extract_section(text, ["next steps", "actions", "recommendations"])

    summary = _first_sentence(summary_body)
    if not summary:
        summary = _first_sentence(text)

    key_points = _extract_bullets(findings_body, limit=4)
    if not key_points:
        key_points = _split_sentences(summary_body, limit=3)

    risks = _extract_bullets(risks_body, limit=3)
    next_steps = _extract_bullets(next_steps_body, limit=3)
    confidence_raw, confidence_label = _confidence_from_text(text)
    sources = _source_count(text)

    headline = title or _first_sentence(summary_body) or str(topic or "Watchtower research card").strip() or "Watchtower research card"
    signal_score = 40
    if summary:
        signal_score += 15
    if key_points:
        signal_score += 20
    if next_steps:
        signal_score += 10
    if risks:
        signal_score += 10
    if confidence_label in {"high", "medium", "low"}:
        signal_score += 5

    flags: list[str] = []
    if not key_points:
        flags.append("missing_key_points")
    if not next_steps:
        flags.append("missing_next_steps")
    if not risks:
        flags.append("missing_risks")
    if confidence_label == "unknown":
        flags.append("missing_confidence")
    if signal_score < 55:
        flags.append("low_signal")

    return {
        "headline": headline[:180],
        "summary": summary[:280],
        "key_points": key_points,
        "risks": risks,
        "next_steps": next_steps,
        "confidence_raw": confidence_raw[:180],
        "confidence_label": confidence_label,
        "source_count": sources,
        "signal_score": max(0, min(100, signal_score)),
        "quality_flags": flags,
    }


LOGGER = logging.getLogger(__name__)


class WatchtowerEngine:
    VALID_SCHEDULES = {"daily", "hourly", "manual"}
    VALID_PROFILES = set(VALID_TOPIC_TYPES)

    def __init__(self, repo_root: Path) -> None:
        self.repo_root = repo_root
        self.watches_path = repo_root / "Runtime" / "watchtower" / "watches.json"
        self.briefing_state_path = repo_root / "Runtime" / "watchtower" / "briefing_state.json"
        self.briefings_dir = repo_root / "Runtime" / "briefings"
        self.repo = WatchtowerRepository(repo_root)
        self._lock = threading.Lock()
        self._stop_event = threading.Event()
        self._thread: threading.Thread | None = None
        self._thread_lock = threading.Lock()
        self._running_watches: set[str] = set()
        self._running_lock = threading.Lock()
        self._briefing_digest_cache: dict[str, tuple[float, dict[str, Any], str]] = {}
        self._briefing_cache_lock = threading.Lock()
        self.scout = WatchtowerScout(repo_root)

        self.watches_path.parent.mkdir(parents=True, exist_ok=True)
        self.briefings_dir.mkdir(parents=True, exist_ok=True)

    # ------------------------------------------------------------------
    # Scheduler
    # ------------------------------------------------------------------

    def start_background_thread(self) -> None:
        with self._thread_lock:
            if self._thread and self._thread.is_alive():
                return
            self._stop_event.clear()
            self._thread = threading.Thread(target=self._scheduler_loop, daemon=True, name="WatchtowerScheduler")
            self._thread.start()

    def _scheduler_loop(self) -> None:
        while not self._stop_event.is_set():
            try:
                for watch in self.list_watches():
                    if watch.get("enabled", True) and self._is_due(watch):
                        watch_id = str(watch.get("id", ""))
                        with self._running_lock:
                            if watch_id in self._running_watches:
                                continue
                            self._running_watches.add(watch_id)
                        threading.Thread(
                            target=self._run_watch_safe,
                            args=(watch,),
                            daemon=True,
                            name=f"WatchtowerRun-{watch_id[:8]}",
                        ).start()
            except Exception:
                LOGGER.exception("Watchtower scheduler loop failed.")
            self._stop_event.wait(60)

    def _is_due(self, watch: dict) -> bool:
        schedule = str(watch.get("schedule", "manual")).strip().lower()
        if schedule == "manual":
            return False
        last_run_raw = str(watch.get("last_run_at", "")).strip()
        now = _now_utc()
        if not last_run_raw:
            if schedule == "daily":
                hour = int(watch.get("schedule_hour", 7))
                return now.hour >= hour
            return True

        try:
            last_run = datetime.fromisoformat(last_run_raw.replace("Z", "+00:00"))
        except ValueError:
            return True

        if schedule == "hourly":
            elapsed = (now - last_run).total_seconds()
            return elapsed >= 3600
        if schedule == "daily":
            hour = int(watch.get("schedule_hour", 7))
            today_run = now.replace(hour=hour, minute=0, second=0, microsecond=0)
            return now >= today_run and last_run < today_run

        return False

    def _run_watch_safe(self, watch: dict) -> None:
        watch_id = str(watch.get("id", ""))
        try:
            self._run_watch(watch)
        except Exception:
            LOGGER.exception("Watchtower watch execution failed for %s.", watch_id)
        finally:
            with self._running_lock:
                self._running_watches.discard(watch_id)

    def _latest_briefing_snapshot(self, watch_id: str) -> dict[str, Any]:
        key = str(watch_id or "").strip()
        if not key:
            return {}
        rows = self.repo.list_briefings(limit=200)
        for row in rows:
            if str(row.get("watch_id", "")).strip() != key:
                continue
            digest, markdown = self._briefing_digest_for_row(row)
            return {
                "created_at": str(row.get("created_at", "")).strip(),
                "summary": str(digest.get("summary", "")).strip() or str(row.get("preview", "")).strip(),
                "markdown": markdown,
            }
        return {}

    def _compose_watch_prompt(self, watch: dict[str, Any], prior: dict[str, Any] | None = None) -> str:
        topic = str(watch.get("topic", "")).strip()
        profile = str(watch.get("profile", "general")).strip().lower() or "general"
        schedule = str(watch.get("schedule", "daily")).strip().lower() or "daily"
        last_run_raw = str(watch.get("last_run_at", "")).strip()

        cadence_hint = "Focus on what changed recently, what matters now, and what to do next."
        if schedule == "hourly":
            cadence_hint = "Prioritize developments from the last 24 hours and immediate operational impact."
        elif schedule == "daily":
            cadence_hint = "Prioritize developments from the last 7 days and near-term implications."
        elif schedule == "manual":
            cadence_hint = "Provide a concise current-state snapshot with practical updates."

        since_hint = (
            f"Last run timestamp (UTC): {last_run_raw}."
            if last_run_raw
            else "No previous run is recorded for this watch."
        )
        prior = prior or {}
        prior_summary = str(prior.get("summary", "")).strip()
        prior_created_at = str(prior.get("created_at", "")).strip()
        prior_hint = (
            f"Previous briefing ({prior_created_at} UTC) summary: {prior_summary}"
            if prior_summary
            else "No previous briefing summary is available."
        )

        return (
            "Create a Watchtower briefing for a recurring monitoring system.\n"
            f"Topic: {topic}\n"
            f"Profile: {profile}\n"
            f"Schedule: {schedule}\n"
            f"{since_hint}\n"
            f"{prior_hint}\n"
            f"{cadence_hint}\n\n"
            "Output markdown with these sections in order:\n"
            "## Executive Summary\n"
            "## Material Changes Since Last Run\n"
            "## Key Findings\n"
            "## Uncertainties & Risks\n"
            "## Next Steps\n"
            "Evidence Confidence: <High|Medium|Low> - one short reason.\n"
            "Rules:\n"
            "- Focus on what changed vs. the prior run. Do not repeat unchanged baseline facts.\n"
            "- If no substantiated update exists, explicitly say: 'No material changes since last run.'\n"
            "- Mention rumor/buzz only if labeled unverified and low-confidence.\n"
            "- Avoid generic filler language; include concrete entities, places, numbers, or dates when available.\n"
            "- Keep each section concise, specific, and decision-oriented."
        )

    def _apply_hourly_no_change_guard(self, watch: dict[str, Any], content: str, prior_markdown: str) -> str:
        schedule = str(watch.get("schedule", "daily")).strip().lower()
        if schedule != "hourly":
            return content
        text = str(content or "").strip()
        if not text:
            return content
        if "material change check" in text.lower():
            return content
        prior_text = str(prior_markdown or "").strip()
        # No baseline means we cannot determine whether this run changed.
        if not prior_text:
            return text

        topic = str(watch.get("topic", "")).strip()
        current = _build_briefing_digest(topic, text)
        previous = _build_briefing_digest(topic, prior_text)
        current_signal = (
            str(current.get("summary", "")) + " " + " ".join(current.get("key_points", []) or [])
        ).strip()
        previous_signal = (
            str(previous.get("summary", "")) + " " + " ".join(previous.get("key_points", []) or [])
        ).strip()
        similarity = _text_similarity(current_signal, previous_signal)
        low_signal = (
            "low_signal" in set(current.get("quality_flags", []) or [])
            or int(current.get("signal_score", 0) or 0) < 60
            or str(current.get("confidence_label", "unknown")).strip().lower() in {"low", "unknown"}
        )
        already_no_change = "no material changes since last run" in text.lower()
        high_overlap = similarity >= 0.9
        if not already_no_change and not (high_overlap and low_signal):
            return text

        run_stamp = _now_iso()
        similarity_pct = int(round(max(0.0, min(1.0, similarity)) * 100))
        note = (
            "## Material Change Check\n"
            "No material changes since last run. Background chatter may exist, including rumors, "
            "but there is no substantial new evidence to act on.\n"
            f"Evidence overlap with prior briefing: {similarity_pct}%\n\n"
            f"Run stamp (UTC): {run_stamp}\n"
        )
        return f"{text.rstrip()}\n\n{note}"

    def _read_briefing_markdown(self, path_value: str) -> str:
        path_text = str(path_value or "").strip()
        if not path_text:
            return ""
        path = Path(path_text)
        if not path.exists() or not path.is_file():
            return ""
        try:
            return path.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            return ""

    def _briefing_digest_for_row(self, row: dict[str, Any]) -> tuple[dict[str, Any], str]:
        path_value = str(row.get("path", "")).strip()
        topic = str(row.get("topic", "")).strip()
        if not path_value:
            return _build_briefing_digest(topic, ""), ""
        path = Path(path_value)
        if not path.exists() or not path.is_file():
            return _build_briefing_digest(topic, ""), ""

        cache_key = str(path.resolve())
        try:
            mtime = float(path.stat().st_mtime)
        except OSError:
            return _build_briefing_digest(topic, ""), ""

        with self._briefing_cache_lock:
            cached = self._briefing_digest_cache.get(cache_key)
            if cached and abs(cached[0] - mtime) < 0.0001:
                return dict(cached[1]), str(cached[2] or "")

        markdown = self._read_briefing_markdown(path_value)
        digest = _build_briefing_digest(topic, markdown)
        with self._briefing_cache_lock:
            self._briefing_digest_cache[cache_key] = (mtime, dict(digest), markdown)
        return digest, markdown

    def _enrich_briefing_row(self, row: dict[str, Any], *, include_markdown: bool = False) -> dict[str, Any]:
        base = dict(row)
        digest, markdown = self._briefing_digest_for_row(base)
        summary = str(digest.get("summary", "")).strip()
        if summary:
            base["preview"] = summary
        base.update(digest)
        if include_markdown:
            base["content_markdown"] = markdown
        return base

    def _run_watch(self, watch: dict) -> None:
        import sys

        source = self.repo_root / "SourceCode"
        if str(source) not in sys.path:
            sys.path.insert(0, str(source))

        from infra.tools import ToolRegistry
        from orchestrator.services.agent_contracts import AgentTask
        from orchestrator.services.agent_registry import ResearchPoolAgent
        from shared_tools.activity_bus import ActivityBus

        watch_id = str(watch.get("id", ""))
        topic = str(watch.get("topic", "")).strip()
        profile = str(watch.get("profile", "general")).strip()
        if not topic:
            return
        prior_snapshot = self._latest_briefing_snapshot(watch_id)

        bus = ActivityBus(self.repo_root)
        bus.emit("watchtower", "watch_started", {"watch_id": watch_id, "topic": topic})

        try:
            tools = ToolRegistry()
            tools.register("bus", bus, description="Watchtower execution bus")
            result = ResearchPoolAgent().run(
                AgentTask(
                    lane="research",
                    prompt=self._compose_watch_prompt(watch, prior_snapshot),
                    project_slug="general",
                    repo_root=self.repo_root,
                    context={"topic_type": profile},
                ),
                tools,
            )
            out = dict(result.payload) if isinstance(result.payload, dict) and result.payload else result.as_dict()
        except Exception as exc:
            bus.emit("watchtower", "watch_failed", {"watch_id": watch_id, "error": str(exc)})
            self._update_watch_last_run(watch_id)
            return

        summary_path = str(out.get("summary_path", "")).strip()
        preview = ""
        briefing_path = ""
        digest: dict[str, Any] = {}
        if summary_path and Path(summary_path).exists():
            try:
                content = Path(summary_path).read_text(encoding="utf-8", errors="ignore")
                content = self._apply_hourly_no_change_guard(
                    watch,
                    content,
                    str(prior_snapshot.get("markdown", "")).strip(),
                )
                digest = _build_briefing_digest(topic, content)
                preview = str(digest.get("summary", "")).strip() or content.strip()[:280]
                ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
                slug = _slug(topic)
                briefing_filename = f"{ts}_{slug}.md"
                briefing_dest = self.briefings_dir / briefing_filename
                briefing_dest.write_text(content, encoding="utf-8")
                briefing_path = str(briefing_dest)
            except Exception:
                briefing_path = summary_path
                preview = ""

        brief_id = f"brief_{uuid.uuid4().hex[:10]}"
        entry = {
            "id": brief_id,
            "watch_id": watch_id,
            "topic": topic,
            "domain": profile,
            "path": briefing_path or summary_path,
            "preview": preview,
            "created_at": _now_iso(),
            "read": False,
        }
        self._save_briefing(entry)
        try:
            self.scout.queue_research_card_from_briefing(
                briefing={
                    **entry,
                    "headline": str(digest.get("headline", "")).strip(),
                    "summary": str(digest.get("summary", "")).strip() or preview,
                }
            )
        except Exception:
            LOGGER.exception("Failed to queue watchtower research card for card %s.", brief_id)
        self._update_watch_last_run(watch_id)
        bus.emit("watchtower", "watch_completed", {"watch_id": watch_id, "card_id": brief_id})

    # ------------------------------------------------------------------
    # Watch CRUD
    # ------------------------------------------------------------------

    def _load_watches(self) -> list[dict]:
        return self.repo.list_watches()

    def _save_watches(self, watches: list[dict]) -> None:
        existing = {str(x.get("id", "")).strip(): x for x in self.repo.list_watches()}
        target = {str(x.get("id", "")).strip(): x for x in watches}
        for watch_id in list(existing):
            if watch_id and watch_id not in target:
                self.repo.delete_watch(watch_id)
        for row in watches:
            wid = str(row.get("id", "")).strip()
            if not wid:
                continue
            if wid in existing:
                self.repo.update_watch(wid, **row)
            else:
                self.repo.add_watch(row)

    def list_watches(self) -> list[dict]:
        with self._lock:
            watches = self.repo.list_watches()
            recent_briefs = self.repo.list_briefings(limit=500)
        by_watch: dict[str, dict[str, Any]] = {}
        for row in recent_briefs:
            wid = str(row.get("watch_id", "")).strip()
            if not wid:
                continue
            state = by_watch.get(wid)
            created_at = str(row.get("created_at", "")).strip()
            if state is None:
                by_watch[wid] = {
                    "card_count": 1,
                    "unread_cards": 0 if bool(row.get("read", False)) else 1,
                    "last_card_at": created_at,
                    "latest_card_preview": str(row.get("preview", "")).strip(),
                }
            else:
                state["card_count"] = int(state.get("card_count", 0)) + 1
                if not bool(row.get("read", False)):
                    state["unread_cards"] = int(state.get("unread_cards", 0)) + 1

        out: list[dict] = []
        for watch in watches:
            wid = str(watch.get("id", "")).strip()
            merged = dict(watch)
            merged["domain"] = str(merged.get("profile", "general")).strip()
            stats = by_watch.get(wid, {})
            merged["card_count"] = int(stats.get("card_count", 0))
            merged["unread_cards"] = int(stats.get("unread_cards", 0))
            merged["last_card_at"] = str(stats.get("last_card_at", "")).strip()
            merged["latest_card_preview"] = str(stats.get("latest_card_preview", "")).strip()
            out.append(merged)
        return out

    def add_watch(
        self,
        *,
        topic: str,
        profile: str = "general",
        schedule: str = "daily",
        schedule_hour: int = 7,
    ) -> dict:
        topic = topic.strip()
        if not topic:
            raise ValueError("Topic cannot be empty.")
        profile = profile.strip().lower()
        if profile not in self.VALID_PROFILES:
            profile = "general"
        schedule = schedule.strip().lower()
        if schedule not in self.VALID_SCHEDULES:
            schedule = "daily"
        schedule_hour = max(0, min(23, int(schedule_hour)))

        watch = {
            "id": f"watch_{uuid.uuid4().hex[:10]}",
            "topic": topic,
            "profile": profile,
            "schedule": schedule,
            "schedule_hour": schedule_hour,
            "enabled": True,
            "last_run_at": "",
            "created_at": _now_iso(),
        }
        with self._lock:
            self.repo.add_watch(watch)
        return self.repo.get_watch(watch["id"]) or watch

    def update_watch(self, watch_id: str, **fields: Any) -> dict | None:
        key = watch_id.strip()
        allowed = {"topic", "profile", "schedule", "schedule_hour", "enabled"}
        clean: dict[str, Any] = {}
        for field, value in fields.items():
            if field not in allowed:
                continue
            if field == "profile":
                value = str(value).strip().lower()
                if value not in self.VALID_PROFILES:
                    value = "general"
            elif field == "schedule":
                value = str(value).strip().lower()
                if value not in self.VALID_SCHEDULES:
                    value = "daily"
            elif field == "schedule_hour":
                value = max(0, min(23, int(value)))
            elif field == "enabled":
                value = bool(value)
            elif field == "topic":
                value = str(value).strip()
            clean[field] = value
        with self._lock:
            return self.repo.update_watch(key, **clean)

    def delete_watch(self, watch_id: str) -> bool:
        key = watch_id.strip()
        with self._lock:
            return self.repo.delete_watch(key)

    def trigger_watch(self, watch_id: str) -> dict:
        watches = self.list_watches()
        target: dict | None = None
        for row in watches:
            if str(row.get("id", "")) == watch_id.strip():
                target = row
                break
        if target is None:
            raise ValueError(f"Watch not found: {watch_id}")
        with self._running_lock:
            if watch_id in self._running_watches:
                return {**target, "status": "already_running"}
            self._running_watches.add(watch_id)
        threading.Thread(
            target=self._run_watch_safe,
            args=(target,),
            daemon=True,
            name=f"WatchtowerTrigger-{watch_id[:8]}",
        ).start()
        return {**target, "status": "triggered"}

    def _update_watch_last_run(self, watch_id: str) -> None:
        with self._lock:
            self.repo.update_watch(watch_id, last_run_at=_now_iso())

    # ------------------------------------------------------------------
    # Briefing state
    # ------------------------------------------------------------------

    def _load_briefing_state(self) -> dict[str, dict]:
        return {str(row.get("id", "")): row for row in self.repo.list_briefings(limit=500)}

    def _save_briefing_state(self, state: dict[str, dict]) -> None:
        target = {str(key): value for key, value in state.items() if isinstance(value, dict)}
        for key, row in target.items():
            payload = dict(row)
            payload["id"] = key
            self.repo.save_briefing(payload)

    def _save_briefing(self, entry: dict) -> None:
        with self._lock:
            self.repo.save_briefing(entry)

    def list_briefings(self, limit: int = 50) -> list[dict]:
        rows = self.repo.list_briefings(limit=limit)
        return [self._enrich_briefing_row(row) for row in rows]

    def list_research_cards(self, limit: int = 50) -> list[dict]:
        return self.list_briefings(limit=limit)

    def get_briefing(self, briefing_id: str) -> dict[str, Any] | None:
        key = briefing_id.strip()
        row = self.repo.get_briefing(key)
        if row is None:
            return None
        return self._enrich_briefing_row(row, include_markdown=True)

    def get_research_card(self, card_id: str) -> dict[str, Any] | None:
        return self.get_briefing(card_id)

    def mark_read(self, briefing_id: str) -> bool:
        key = briefing_id.strip()
        with self._lock:
            return self.repo.mark_read(key)

    def mark_research_card_read(self, card_id: str) -> bool:
        return self.mark_read(card_id)

    def mark_unread(self, briefing_id: str) -> bool:
        key = briefing_id.strip()
        with self._lock:
            return self.repo.mark_unread(key)

    def mark_research_card_unread(self, card_id: str) -> bool:
        return self.mark_unread(card_id)

    def unread_count(self) -> int:
        with self._lock:
            return self.repo.unread_count()

    def list_cards(self, *, limit: int = 100, card_type: str = "", status: str = "") -> list[dict[str, Any]]:
        return self.scout.card_store.list_cards(limit=limit, card_type=card_type, status=status)

    def get_card(self, card_id: str) -> dict[str, Any] | None:
        return self.scout.card_store.get_card(card_id)

    def set_card_status(self, card_id: str, *, status: str, note: str = "") -> dict[str, Any] | None:
        return self.scout.card_store.set_status(card_id, status=status, note=note)

    def scan_project_gaps(
        self,
        *,
        project: str = "general",
        project_kernel: dict[str, Any] | None = None,
        auditor_report: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        kernel = dict(project_kernel or {})
        if not kernel:
            from core.project_kernel import ProjectKernelStore

            kernel = ProjectKernelStore(self.repo_root).snapshot(project)
        report = dict(auditor_report or {})
        if not report:
            report = self._latest_auditor_report()
        return self.scout.scan_project(project=project, project_kernel=kernel, auditor_report=report)

    def _latest_auditor_report(self) -> dict[str, Any]:
        index_path = self.repo_root / "Runtime" / "auditor" / "regression_reports" / "reports.jsonl"
        if not index_path.exists():
            return {}
        lines = index_path.read_text(encoding="utf-8").splitlines()
        for line in reversed(lines):
            text = str(line or "").strip()
            if not text:
                continue
            try:
                row = json.loads(text)
            except Exception:
                continue
            path = str(row.get("path", "")).strip()
            if not path:
                continue
            report_path = self.repo_root / path
            if not report_path.exists():
                continue
            try:
                payload = json.loads(report_path.read_text(encoding="utf-8"))
            except Exception:
                continue
            if isinstance(payload, dict):
                return payload
        return {}

    def recent_briefing_context(self, limit: int = 2, max_chars: int = 600) -> str:
        """Return a brief context block from the most recent unread research cards.

        Designed for injection into agent prompts. Returns empty string if no
        unread briefings exist or on any error.
        """
        try:
            rows = self.repo.list_briefings(limit=20)
        except Exception:
            return ""
        unread = [r for r in rows if not bool(r.get("read", False))][:limit]
        if not unread:
            return ""
        lines: list[str] = ["[Watchtower — recent unread research cards]"]
        chars_used = len(lines[0])
        for row in unread:
            try:
                digest, _ = self._briefing_digest_for_row(row)
            except Exception:
                continue
            topic = str(row.get("topic", "")).strip() or "research card"
            headline = str(digest.get("headline", "")).strip() or topic
            summary = str(digest.get("summary", "")).strip()
            key_points = list(digest.get("key_points") or [])
            entry_parts = [f"• {headline}"]
            if summary:
                entry_parts.append(f"  {summary}")
            for pt in key_points[:2]:
                entry_parts.append(f"  - {str(pt).strip()}")
            entry = "\n".join(entry_parts)
            if chars_used + len(entry) + 1 > max_chars:
                break
            lines.append(entry)
            chars_used += len(entry) + 1
        return "\n".join(lines) if len(lines) > 1 else ""

    def recent_queued_card_context(self, limit: int = 2, max_chars: int = 600) -> str:
        try:
            cards = self.list_cards(limit=max(10, limit * 4), status="queued")
        except Exception:
            return ""
        if not cards:
            return ""
        lines: list[str] = ["[Watchtower — queued research cards]"]
        chars_used = len(lines[0])
        for row in cards[: max(1, int(limit))]:
            title = str(row.get("title", "")).strip() or "Watchtower card"
            summary = str(row.get("summary", "")).strip()
            scope = row.get("scope", {}) if isinstance(row.get("scope", {}), dict) else {}
            domain = str(scope.get("domain", "")).strip()
            topic = str(scope.get("topic", "")).strip()
            scope_hint = " / ".join([x for x in (domain, topic) if x]) or str(row.get("scope_level", "")).strip()
            entry = f"• {title}"
            if scope_hint:
                entry += f" ({scope_hint})"
            if summary:
                entry += f"\n  {summary}"
            if chars_used + len(entry) + 1 > max_chars:
                break
            lines.append(entry)
            chars_used += len(entry) + 1
        return "\n".join(lines) if len(lines) > 1 else ""

    def recent_research_card_context(self, limit: int = 2, max_chars: int = 600) -> str:
        briefing = self.recent_briefing_context(limit=limit, max_chars=max_chars)
        remaining = max(120, max_chars - len(briefing)) if briefing else max_chars
        queued = self.recent_queued_card_context(limit=limit, max_chars=remaining)
        if briefing and queued:
            combined = briefing + "\n\n" + queued
            return combined[:max_chars].rstrip()
        return briefing or queued
