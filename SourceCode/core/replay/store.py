from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


class ReplayStore:
    """Deterministic replay artifact store for pipeline runs."""

    def __init__(self, repo_root: Path) -> None:
        self.repo_root = Path(repo_root)
        self.root = self.repo_root / "Runtime" / "replay"
        self.root.mkdir(parents=True, exist_ok=True)
        self.index_path = self.root / "replay_index.jsonl"
        if not self.index_path.exists():
            self.index_path.write_text("", encoding="utf-8")

    def save_bundle(
        self,
        *,
        run_id: str,
        project: str,
        pipeline: str,
        model_settings: dict[str, Any],
        input_payload: dict[str, Any],
        context_packs: dict[str, dict[str, Any]],
        stage_outputs: dict[str, dict[str, Any]],
        stage_audits: dict[str, dict[str, Any]],
        stage_timings_ms: dict[str, int],
        hardware_profile: dict[str, Any],
        promoted_memory_ids: list[str],
        started_at: str,
        finished_at: str,
    ) -> dict[str, Any]:
        bundle = {
            "run_id": str(run_id),
            "project": str(project),
            "pipeline": str(pipeline),
            "model_settings": dict(model_settings or {}),
            "input_payload": dict(input_payload or {}),
            "context_packs": {str(k): dict(v) for k, v in (context_packs or {}).items() if isinstance(v, dict)},
            "stage_outputs": {str(k): dict(v) for k, v in (stage_outputs or {}).items() if isinstance(v, dict)},
            "stage_audits": {str(k): dict(v) for k, v in (stage_audits or {}).items() if isinstance(v, dict)},
            "stage_timings_ms": {str(k): int(v or 0) for k, v in (stage_timings_ms or {}).items()},
            "hardware_profile": dict(hardware_profile or {}),
            "promoted_memory_ids": [str(x) for x in promoted_memory_ids if str(x).strip()],
            "started_at": str(started_at or ""),
            "finished_at": str(finished_at or ""),
            "created_at": _now_iso(),
        }

        replay_dir = self.root / str(run_id)
        replay_dir.mkdir(parents=True, exist_ok=True)
        replay_file = replay_dir / "bundle.json"
        replay_file.write_text(json.dumps(bundle, indent=2, ensure_ascii=True), encoding="utf-8")

        index_row = {
            "event": "replay_bundle_saved",
            "run_id": str(run_id),
            "project": str(project),
            "pipeline": str(pipeline),
            "path": str(replay_file.relative_to(self.repo_root)),
            "created_at": bundle["created_at"],
        }
        with self.index_path.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(index_row, ensure_ascii=True))
            fh.write("\n")
        return bundle

    def load_bundle(self, run_id: str) -> dict[str, Any]:
        key = str(run_id or "").strip()
        if not key:
            return {}
        path = self.root / key / "bundle.json"
        if not path.exists():
            return {}
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            return {}
        return dict(payload) if isinstance(payload, dict) else {}
