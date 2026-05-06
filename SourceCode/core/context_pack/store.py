from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .schema import ContextPack, build_context_pack


class ContextPackStore:
    """Persistent store for compiled context packs."""

    def __init__(self, repo_root: Path) -> None:
        self.repo_root = Path(repo_root)
        self.root = self.repo_root / "Runtime" / "context_packs"
        self.root.mkdir(parents=True, exist_ok=True)
        self.index_path = self.root / "context_packs.jsonl"
        if not self.index_path.exists():
            self.index_path.write_text("", encoding="utf-8")

    def persist(self, payload: dict[str, Any] | ContextPack) -> dict[str, Any]:
        pack = payload if isinstance(payload, ContextPack) else build_context_pack(payload)
        row = pack.as_dict()
        run_id = str(row.get("run_id", "")).strip() or "unknown_run"
        stage = str(row.get("stage", "")).strip() or "unknown_stage"
        context_pack_id = str(row.get("context_pack_id", "")).strip() or "unknown_context_pack"
        run_root = self.root / run_id
        run_root.mkdir(parents=True, exist_ok=True)
        stage_file = run_root / f"{stage}__{context_pack_id}.json"
        stage_file.write_text(json.dumps(row, indent=2, ensure_ascii=True), encoding="utf-8")

        index_row = {
            "event": "context_pack_persisted",
            "context_pack_id": context_pack_id,
            "run_id": run_id,
            "pipeline": str(row.get("pipeline", "")).strip(),
            "stage": stage,
            "project": str(row.get("project", "")).strip(),
            "path": str(stage_file.relative_to(self.repo_root)),
            "created_at": str(row.get("created_at", "")).strip(),
        }
        with self.index_path.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(index_row, ensure_ascii=True))
            fh.write("\n")
        return row
