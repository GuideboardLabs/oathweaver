from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


class RegressionReporter:
    """Persists typed auditor reports for regression tracking."""

    def __init__(self, repo_root: Path) -> None:
        self.repo_root = Path(repo_root)
        self.root = self.repo_root / "Runtime" / "auditor" / "regression_reports"
        self.root.mkdir(parents=True, exist_ok=True)
        self.index_path = self.root / "reports.jsonl"
        if not self.index_path.exists():
            self.index_path.write_text("", encoding="utf-8")

    def write_report(self, report: dict[str, Any]) -> dict[str, Any]:
        payload = dict(report or {})
        run_id = str(payload.get("run_id", "")).strip() or "unknown_run"
        out_dir = self.root / run_id
        out_dir.mkdir(parents=True, exist_ok=True)
        out_file = out_dir / "report.json"
        payload.setdefault("created_at", _now_iso())
        out_file.write_text(json.dumps(payload, indent=2, ensure_ascii=True), encoding="utf-8")

        index_row = {
            "event": "auditor_report_written",
            "run_id": run_id,
            "pipeline": str(payload.get("pipeline", "")).strip(),
            "typed_finding_count": len(payload.get("typed_findings", []) if isinstance(payload.get("typed_findings", []), list) else []),
            "path": str(out_file.relative_to(self.repo_root)),
            "created_at": payload.get("created_at", _now_iso()),
        }
        with self.index_path.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(index_row, ensure_ascii=True))
            fh.write("\n")
        return payload
