from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


class StateStore:
    """Transient run-state store for deterministic pipeline execution."""

    def __init__(self, repo_root: Path) -> None:
        self.repo_root = Path(repo_root)
        self.root = self.repo_root / "Runtime" / "state"
        self.root.mkdir(parents=True, exist_ok=True)
        self.events_path = self.root / "pipeline_state.jsonl"
        self.index_path = self.root / "pipeline_state_index.json"

    def start_run(self, *, project: str, pipeline: str, input_contract: dict[str, Any]) -> str:
        run_id = f"run_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}_{uuid.uuid4().hex[:8]}"
        payload = {
            "event": "run_started",
            "run_id": run_id,
            "project": str(project or "general"),
            "pipeline": str(pipeline or ""),
            "input_contract": dict(input_contract or {}),
            "created_at": _now_iso(),
        }
        self._append_event(payload)
        self._update_index(run_id, payload)
        return run_id

    def write_stage_state(
        self,
        *,
        run_id: str,
        stage: str,
        state: dict[str, Any],
        contract_audit: dict[str, Any] | None = None,
        context_pack: dict[str, Any] | None = None,
        on_deck_plan: dict[str, Any] | None = None,
    ) -> None:
        payload = {
            "event": "stage_completed",
            "run_id": str(run_id),
            "stage": str(stage),
            "state": dict(state or {}),
            "contract_audit": dict(contract_audit or {}),
            "context_pack": dict(context_pack or {}),
            "on_deck_plan": dict(on_deck_plan or {}),
            "created_at": _now_iso(),
        }
        self._append_event(payload)
        self._update_index(run_id, payload)

    def finalize_run(self, *, run_id: str, ok: bool, final_state: dict[str, Any]) -> None:
        payload = {
            "event": "run_finished",
            "run_id": str(run_id),
            "ok": bool(ok),
            "final_state": dict(final_state or {}),
            "created_at": _now_iso(),
        }
        self._append_event(payload)
        self._update_index(run_id, payload)

    def latest_run_state(self, run_id: str) -> dict[str, Any]:
        key = str(run_id or "").strip()
        if not key or not self.index_path.exists():
            return {}
        try:
            payload = json.loads(self.index_path.read_text(encoding="utf-8"))
        except Exception:
            return {}
        if not isinstance(payload, dict):
            return {}
        row = payload.get(key, {})
        return dict(row) if isinstance(row, dict) else {}

    def _append_event(self, payload: dict[str, Any]) -> None:
        with self.events_path.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(payload, ensure_ascii=True))
            fh.write("\n")

    def _update_index(self, run_id: str, event_payload: dict[str, Any]) -> None:
        row: dict[str, Any] = {}
        if self.index_path.exists():
            try:
                parsed = json.loads(self.index_path.read_text(encoding="utf-8"))
                if isinstance(parsed, dict):
                    row = parsed
            except Exception:
                row = {}
        run_key = str(run_id)
        existing = row.get(run_key, {}) if isinstance(row.get(run_key, {}), dict) else {}
        merged = dict(existing)
        merged["run_id"] = run_key
        merged["updated_at"] = _now_iso()
        merged["last_event"] = dict(event_payload)
        row[run_key] = merged
        self.index_path.write_text(json.dumps(row, indent=2, ensure_ascii=True), encoding="utf-8")
