from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


_VALID_CARD_TYPES = {
    "research_card",
    "knowledge_gap_card",
    "benchmark_gap_card",
    "capability_gap_card",
}

_VALID_CARD_STATUSES = {
    "queued",
    "accepted",
    "rejected",
    "running",
    "completed",
}


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _normalize_text(value: Any) -> str:
    return str(value or "").strip()


class ResearchCardStore:
    """Queued proposal store for watchtower cards.

    Cards are intentionally separate from CAG memory rows. This preserves
    phase-9 semantics: watchtower can propose work, but never silently mutates CAG.
    """

    def __init__(self, repo_root: Path) -> None:
        self.repo_root = Path(repo_root)
        self.root = self.repo_root / "Runtime" / "watchtower"
        self.root.mkdir(parents=True, exist_ok=True)
        self.state_path = self.root / "cards_state.json"
        self.events_path = self.root / "cards_events.jsonl"
        if not self.state_path.exists():
            self.state_path.write_text("{}", encoding="utf-8")
        if not self.events_path.exists():
            self.events_path.write_text("", encoding="utf-8")

    def queue_card(self, payload: dict[str, Any]) -> dict[str, Any]:
        now = _now_iso()
        card_id = _normalize_text(payload.get("id")) or f"card_{uuid.uuid4().hex[:12]}"
        card_type = _normalize_text(payload.get("card_type")).lower() or "knowledge_gap_card"
        if card_type not in _VALID_CARD_TYPES:
            card_type = "knowledge_gap_card"
        status = _normalize_text(payload.get("status")).lower() or "queued"
        if status not in _VALID_CARD_STATUSES:
            status = "queued"

        scope = payload.get("scope", {}) if isinstance(payload.get("scope", {}), dict) else {}
        scope_level = _normalize_text(payload.get("scope_level")).lower() or _normalize_text(scope.get("scope_level")).lower()
        if scope_level not in {"domain", "topic", "thread", "project"}:
            scope_level = "project"

        state = self._load_state()
        existing = state.get(card_id, {}) if isinstance(state.get(card_id, {}), dict) else {}
        created_at = _normalize_text(existing.get("created_at")) or _normalize_text(payload.get("created_at")) or now

        row = {
            "id": card_id,
            "card_type": card_type,
            "status": status,
            "scope_level": scope_level,
            "scope": {
                "domain": _normalize_text(scope.get("domain")),
                "topic": _normalize_text(scope.get("topic")),
                "thread": _normalize_text(scope.get("thread")),
                "project": _normalize_text(scope.get("project")),
                "run": _normalize_text(scope.get("run")),
            },
            "title": _normalize_text(payload.get("title")) or "Watchtower card",
            "summary": _normalize_text(payload.get("summary")),
            "recommended_action": _normalize_text(payload.get("recommended_action")),
            "evidence": [dict(x) for x in payload.get("evidence", []) if isinstance(x, dict)],
            "priority": _normalize_text(payload.get("priority")).lower() or "medium",
            "source": _normalize_text(payload.get("source")) or "watchtower",
            "linked_run_id": _normalize_text(payload.get("linked_run_id")),
            "created_at": created_at,
            "updated_at": now,
            "decision_note": _normalize_text(payload.get("decision_note")),
        }

        state[card_id] = row
        self._save_state(state)
        self._append_event({"event": "card_queued", "card": row, "created_at": now})
        return dict(row)

    def get_card(self, card_id: str) -> dict[str, Any] | None:
        key = _normalize_text(card_id)
        if not key:
            return None
        state = self._load_state()
        row = state.get(key)
        return dict(row) if isinstance(row, dict) else None

    def list_cards(
        self,
        *,
        limit: int = 100,
        card_type: str = "",
        status: str = "",
    ) -> list[dict[str, Any]]:
        wanted_type = _normalize_text(card_type).lower()
        wanted_status = _normalize_text(status).lower()
        rows = [dict(x) for x in self._load_state().values() if isinstance(x, dict)]
        if wanted_type:
            rows = [x for x in rows if _normalize_text(x.get("card_type")).lower() == wanted_type]
        if wanted_status:
            rows = [x for x in rows if _normalize_text(x.get("status")).lower() == wanted_status]
        rows.sort(key=lambda x: _normalize_text(x.get("created_at")), reverse=True)
        return rows[: max(1, int(limit))]

    def set_status(self, card_id: str, *, status: str, note: str = "") -> dict[str, Any] | None:
        key = _normalize_text(card_id)
        if not key:
            return None
        normalized_status = _normalize_text(status).lower()
        if normalized_status not in _VALID_CARD_STATUSES:
            return None

        state = self._load_state()
        row = state.get(key)
        if not isinstance(row, dict):
            return None

        row = dict(row)
        row["status"] = normalized_status
        if note.strip():
            row["decision_note"] = note.strip()
        row["updated_at"] = _now_iso()
        state[key] = row
        self._save_state(state)
        self._append_event(
            {
                "event": "card_status_changed",
                "card_id": key,
                "status": normalized_status,
                "decision_note": _normalize_text(note),
                "created_at": row["updated_at"],
            }
        )
        return row

    def summarize(self) -> dict[str, int]:
        rows = self.list_cards(limit=10000)
        summary = {
            "total": len(rows),
            "queued": 0,
            "accepted": 0,
            "rejected": 0,
            "running": 0,
            "completed": 0,
        }
        for row in rows:
            status = _normalize_text(row.get("status")).lower()
            if status in summary:
                summary[status] += 1
        return summary

    def _load_state(self) -> dict[str, dict[str, Any]]:
        try:
            payload = json.loads(self.state_path.read_text(encoding="utf-8"))
        except Exception:
            return {}
        if not isinstance(payload, dict):
            return {}
        out: dict[str, dict[str, Any]] = {}
        for key, value in payload.items():
            if isinstance(value, dict):
                out[str(key)] = dict(value)
        return out

    def _save_state(self, state: dict[str, dict[str, Any]]) -> None:
        self.state_path.write_text(json.dumps(state, indent=2, ensure_ascii=True), encoding="utf-8")

    def _append_event(self, payload: dict[str, Any]) -> None:
        with self.events_path.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(payload, ensure_ascii=True))
            fh.write("\n")
