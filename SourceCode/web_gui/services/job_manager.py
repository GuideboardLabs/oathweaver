"""Job lifecycle management — tracks in-flight message processing jobs."""

from __future__ import annotations

import re
import threading
import uuid
from datetime import datetime, timezone
from typing import Any


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


class JobManager:
    """Thread-safe registry for in-flight message jobs.

    Each job is keyed by ``{profile_id}:{request_id}`` and tracks stage,
    events, status, cancel requests, and artifact paths.
    """

    _MAX_EVENTS = 24

    def __init__(self) -> None:
        self._jobs: dict[str, dict[str, Any]] = {}
        self._lock = threading.Lock()

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _key(self, profile: dict[str, Any], request_id: str) -> str:
        uid = str(profile.get("id", "")).strip() or "owner"
        rid = re.sub(r"[^A-Za-z0-9_-]+", "", str(request_id or "").strip())[:72]
        return f"{uid}:{rid}"

    @staticmethod
    def _trim_events(events: list[dict[str, Any]], limit: int = 24) -> list[dict[str, Any]]:
        if len(events) <= limit:
            return events
        return events[-limit:]

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def start(
        self,
        *,
        profile: dict[str, Any],
        conversation_id: str,
        request_id: str,
        mode: str,
        user_text: str,
    ) -> str:
        """Register a new job and return the sanitised request_id."""
        rid = re.sub(r"[^A-Za-z0-9_-]+", "", str(request_id or "").strip())[:72] or uuid.uuid4().hex[:16]
        key = self._key(profile, rid)
        now = _now_iso()
        with self._lock:
            self._jobs[key] = {
                "request_id": rid,
                "profile_id": str(profile.get("id", "")).strip(),
                "conversation_id": str(conversation_id).strip(),
                "mode": str(mode or "command").strip().lower() or "command",
                "started_at": now,
                "updated_at": now,
                "stage": "queued",
                "cancel_requested": False,
                "cancel_requested_at": "",
                "events": [],
                "summary_path": "",
                "raw_path": "",
                "web_stack": {},
                "live_sources": [],
                "status": "running",
                "user_text_preview": str(user_text or "").strip()[:280],
            }
        return rid

    def update(
        self,
        profile: dict[str, Any],
        request_id: str,
        *,
        stage: str,
        detail: str = "",
        summary_path: str = "",
        raw_path: str = "",
        web_stack: dict | None = None,
        agent_event: dict | None = None,
    ) -> None:
        key = self._key(profile, request_id)
        with self._lock:
            row = self._jobs.get(key)
            if not isinstance(row, dict):
                return
            row["updated_at"] = _now_iso()
            row["stage"] = str(stage or "").strip() or str(row.get("stage", "running"))
            if summary_path:
                row["summary_path"] = str(summary_path).strip()
            if raw_path:
                row["raw_path"] = str(raw_path).strip()
            if web_stack and isinstance(web_stack, dict):
                row["web_stack"] = web_stack
            if agent_event and isinstance(agent_event, dict):
                tracker = row.get("agent_tracker")
                if not isinstance(tracker, dict):
                    tracker = {
                        "total": 0, "profile": "", "topic_type": "", "workers": 1,
                        "all_agents": [], "active": [], "done": [],
                    }
                ae_stage = str(agent_event.get("stage", "")).strip()
                if ae_stage == "research_pool_started":
                    tracker["total"] = int(agent_event.get("agents_total", 0))
                    tracker["profile"] = str(agent_event.get("analysis_profile", "")).strip().replace("_", " ")
                    tracker["topic_type"] = str(agent_event.get("topic_type", "")).strip()
                    tracker["workers"] = int(agent_event.get("workers", 1))
                    tracker["all_agents"] = list(agent_event.get("agents", []))
                    tracker["active"] = []
                    tracker["done"] = []
                elif ae_stage == "research_agent_started":
                    persona = str(agent_event.get("agent", "")).strip()
                    if persona and persona not in tracker["active"]:
                        tracker["active"].append({
                            "persona": persona,
                            "directive": str(agent_event.get("directive", "")).strip(),
                            "role": str(agent_event.get("role", "primary")).strip(),
                            "model": str(agent_event.get("model", "")).strip(),
                            "started_at": row["updated_at"],
                        })
                elif ae_stage == "research_agent_completed":
                    persona = str(agent_event.get("agent", "")).strip()
                    tracker["active"] = [
                        a for a in tracker["active"]
                        if (a.get("persona") if isinstance(a, dict) else a) != persona
                    ]
                    if persona:
                        tracker["done"].append({
                            "persona": persona,
                            "failed": bool(agent_event.get("failed", False)),
                            "role": str(agent_event.get("role", "primary")).strip(),
                            "finding_preview": str(agent_event.get("finding_preview", "")).strip()[:400],
                            "confidence": int(agent_event.get("confidence", 0)),
                            "completed_at": row["updated_at"],
                        })
                # Build lane events — mirror of research events for the Build panel
                elif ae_stage == "build_pool_started":
                    tracker["total"] = int(agent_event.get("agents_total", 0))
                    tracker["profile"] = str(agent_event.get("make_type", "")).strip().replace("_", " ")
                    tracker["topic_type"] = str(agent_event.get("destination", "")).strip()
                    tracker["workers"] = int(agent_event.get("workers", 1))
                    tracker["all_agents"] = [
                        {"persona": f"stage-{i+1}", "directive": "", "role": "primary"}
                        for i in range(tracker["total"])
                    ]
                    tracker["active"] = []
                    tracker["done"] = []
                elif ae_stage == "build_agent_started":
                    agent_name = str(agent_event.get("agent", "")).strip()
                    model = str(agent_event.get("model", "")).strip()
                    if agent_name and not any(
                        (a.get("persona") if isinstance(a, dict) else a) == agent_name
                        for a in tracker["active"]
                    ):
                        tracker["active"].append({
                            "persona": agent_name,
                            "directive": str(agent_event.get("directive", "")).strip(),
                            "role": "primary",
                            "model": model,
                            "started_at": row["updated_at"],
                        })
                elif ae_stage == "build_agent_completed":
                    agent_name = str(agent_event.get("agent", "")).strip()
                    tracker["active"] = [
                        a for a in tracker["active"]
                        if (a.get("persona") if isinstance(a, dict) else a) != agent_name
                    ]
                    if agent_name:
                        output_chars = int(agent_event.get("output_chars", 0))
                        tracker["done"].append({
                            "persona": agent_name,
                            "failed": bool(agent_event.get("failed", False)),
                            "role": "primary",
                            "finding_preview": f"{output_chars:,} chars" if output_chars else str(agent_event.get("files", "")) + " files",
                            "confidence": 5 if not agent_event.get("failed") else 1,
                            "completed_at": row["updated_at"],
                        })
                elif ae_stage == "build_quality_gate_passed":
                    tracker["done"].append({
                        "persona": "quality-gate",
                        "failed": False,
                        "role": "primary",
                        "finding_preview": "All quality checks passed.",
                        "confidence": 5,
                        "completed_at": row["updated_at"],
                    })
                elif ae_stage == "build_quality_gate_failed":
                    issues = list(agent_event.get("issues", []))
                    tracker["done"].append({
                        "persona": "quality-gate",
                        "failed": True,
                        "role": "primary",
                        "finding_preview": "; ".join(issues)[:300],
                        "confidence": 2,
                        "completed_at": row["updated_at"],
                    })
                row["agent_tracker"] = tracker
            events = row.get("events", [])
            if not isinstance(events, list):
                events = []
            events.append({
                "ts": row["updated_at"],
                "stage": row["stage"],
                "detail": str(detail or "").strip()[:400],
            })
            row["events"] = self._trim_events(events)

    def append_live_source(self, profile: dict[str, Any], request_id: str, source: dict[str, Any]) -> None:
        """Append a newly-crawled source to the job's live_sources list for real-time UI display."""
        if not isinstance(source, dict):
            return
        key = self._key(profile, request_id)
        with self._lock:
            row = self._jobs.get(key)
            if not isinstance(row, dict):
                return
            ls: list[dict[str, Any]] = row.get("live_sources", [])
            if not isinstance(ls, list):
                ls = []
            ls.append({
                "url": str(source.get("url", "")).strip(),
                "domain": str(source.get("domain", "")).strip(),
                "title": str(source.get("title", "")).strip()[:120],
            })
            row["live_sources"] = ls[-12:]  # keep last 12
            row["updated_at"] = _now_iso()

    def is_cancel_requested(self, profile: dict[str, Any], request_id: str) -> bool:
        key = self._key(profile, request_id)
        with self._lock:
            row = self._jobs.get(key)
            if not isinstance(row, dict):
                return False
            return bool(row.get("cancel_requested", False))

    def request_cancel(self, profile: dict[str, Any], request_id: str) -> tuple[bool, str]:
        key = self._key(profile, request_id)
        with self._lock:
            row = self._jobs.get(key)
            if not isinstance(row, dict):
                return False, "Job not found."
            if str(row.get("status", "")) != "running":
                return False, "Job is no longer running."
            row["cancel_requested"] = True
            row["cancel_requested_at"] = _now_iso()
            row["updated_at"] = row["cancel_requested_at"]
            row["stage"] = "cancel_requested"
            events = row.get("events", [])
            if not isinstance(events, list):
                events = []
            events.append({"ts": row["updated_at"], "stage": "cancel_requested", "detail": "User pressed cancel."})
            row["events"] = self._trim_events(events)
            summary = self.progress_text(row)
        return True, summary

    def finish(
        self,
        profile: dict[str, Any],
        request_id: str,
        *,
        status: str,
        detail: str = "",
        summary_path: str = "",
        raw_path: str = "",
    ) -> None:
        key = self._key(profile, request_id)
        with self._lock:
            row = self._jobs.get(key)
            if not isinstance(row, dict):
                return
            row["status"] = str(status or "completed").strip().lower() or "completed"
            row["updated_at"] = _now_iso()
            row["stage"] = row["status"]
            if summary_path:
                row["summary_path"] = str(summary_path).strip()
            if raw_path:
                row["raw_path"] = str(raw_path).strip()
            events = row.get("events", [])
            if not isinstance(events, list):
                events = []
            if detail:
                events.append({"ts": row["updated_at"], "stage": row["status"], "detail": str(detail)[:400]})
            row["events"] = self._trim_events(events)

    def get(self, profile: dict[str, Any], request_id: str) -> dict[str, Any] | None:
        key = self._key(profile, request_id)
        with self._lock:
            return dict(self._jobs.get(key) or {}) or None

    def progress_text(self, job: dict[str, Any]) -> str:
        stage = str(job.get("stage", "")).strip() or "unknown"
        started_at = str(job.get("started_at", "")).strip()
        request_id = str(job.get("request_id", "")).strip()
        lines = [
            f"Job id: {request_id or 'n/a'}",
            f"Current stage: {stage}",
            f"Started at: {started_at or 'n/a'}",
        ]
        events = job.get("events", [])
        if isinstance(events, list) and events:
            lines.append("Recent checkpoints:")
            for row in events[-6:]:
                if not isinstance(row, dict):
                    continue
                ts = str(row.get("ts", "")).strip()
                label = str(row.get("stage", "")).strip()
                detail = str(row.get("detail", "")).strip()
                if detail:
                    lines.append(f"- [{ts}] {label}: {detail}")
                else:
                    lines.append(f"- [{ts}] {label}")
        summary_path = str(job.get("summary_path", "")).strip()
        raw_path = str(job.get("raw_path", "")).strip()
        if summary_path:
            lines.append(f"Latest summary path: {summary_path}")
        if raw_path:
            lines.append(f"Latest raw path: {raw_path}")
        return "\n".join(lines)

    def key(self, profile: dict[str, Any], request_id: str) -> str:
        """Public key accessor (used by ForagingManager for cross-lookup)."""
        return self._key(profile, request_id)

    def snapshot(self, key: str) -> dict[str, Any]:
        """Return a copy of the job at the given key (for ForagingManager row building)."""
        with self._lock:
            return dict(self._jobs.get(key) or {})
