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

    def latest_snapshot(self) -> dict[str, Any]:
        if not self.events_path.exists():
            return {}
        try:
            lines = self.events_path.read_text(encoding="utf-8").splitlines()
        except Exception:
            return {}
        for line in reversed(lines[-500:]):
            text = str(line or "").strip()
            if not text:
                continue
            try:
                row = json.loads(text)
            except Exception:
                continue
            if str(row.get("event", "")).strip() != "bench_snapshot":
                continue
            snap = row.get("snapshot", {})
            return dict(snap) if isinstance(snap, dict) else {}
        return {}

    def recommended_stage_budget(self, *, default_budget: int) -> int:
        budget = max(256, int(default_budget))
        snapshot = self.latest_snapshot()
        tiers = snapshot.get("tiers", {}) if isinstance(snapshot.get("tiers", {}), dict) else {}
        on_deck = tiers.get("ram_on_deck", []) if isinstance(tiers.get("ram_on_deck", []), list) else []
        warm = tiers.get("ram_warm", []) if isinstance(tiers.get("ram_warm", []), list) else []
        cold = tiers.get("ssd_cold", []) if isinstance(tiers.get("ssd_cold", []), list) else []
        pressure = len(cold) - (len(on_deck) + len(warm))
        if pressure >= 3:
            return max(256, int(round(budget * 0.8)))
        if pressure <= -2:
            return max(256, int(round(budget * 1.1)))
        return budget

    def _append_event(self, payload: dict[str, Any]) -> None:
        with self.events_path.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(payload, ensure_ascii=True))
            fh.write("\n")
