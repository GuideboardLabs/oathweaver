from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


class BenchManager:
    """Tracks hot-seat/on-deck/warm/cold scheduling snapshots."""

    def __init__(self, repo_root: Path) -> None:
        self.repo_root = Path(repo_root)
        self.root = self.repo_root / "Runtime" / "scheduler"
        self.root.mkdir(parents=True, exist_ok=True)
        self.events_path = self.root / "bench_events.jsonl"
        if not self.events_path.exists():
            self.events_path.write_text("", encoding="utf-8")

    def build_snapshot(
        self,
        *,
        run_id: str,
        pipeline: str,
        stage: str,
        current_manifest: dict[str, Any],
        on_deck_entries: list[dict[str, Any]],
        warm_entries: list[dict[str, Any]],
        cold_entries: list[dict[str, Any]],
    ) -> dict[str, Any]:
        snapshot = {
            "run_id": str(run_id),
            "pipeline": str(pipeline),
            "stage": str(stage),
            "tiers": {
                "vram_hot_seat": dict(current_manifest or {}),
                "ram_on_deck": [dict(x) for x in on_deck_entries],
                "ram_warm": [dict(x) for x in warm_entries],
                "ssd_cold": [dict(x) for x in cold_entries],
            },
            "created_at": _now_iso(),
        }
        self._append_event({"event": "bench_snapshot", "snapshot": snapshot})
        return snapshot

    def _append_event(self, payload: dict[str, Any]) -> None:
        with self.events_path.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(payload, ensure_ascii=True))
            fh.write("\n")
