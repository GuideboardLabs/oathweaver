from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _approx_tokens(text: str) -> int:
    words = [w for w in str(text or "").split() if w.strip()]
    if not words:
        return 0
    return max(1, int(round(len(words) * 1.35)))


class TraceLedger:
    """Structured run trace ledger for auditability and training-data extraction."""

    def __init__(self, repo_root: Path) -> None:
        self.repo_root = Path(repo_root)
        self.root = self.repo_root / "Runtime" / "trace_ledger"
        self.root.mkdir(parents=True, exist_ok=True)
        self.events_path = self.root / "runs.jsonl"
        if not self.events_path.exists():
            self.events_path.write_text("", encoding="utf-8")

    def build_stage_rows(
        self,
        *,
        stage_outputs: dict[str, dict[str, Any]],
        context_packs: dict[str, dict[str, Any]],
        stage_timings_ms: dict[str, int],
        stage_audits: dict[str, dict[str, Any]],
    ) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        for stage, output in stage_outputs.items():
            out = dict(output or {})
            pack = dict(context_packs.get(stage, {})) if isinstance(context_packs.get(stage, {}), dict) else {}
            audit = dict(stage_audits.get(stage, {})) if isinstance(stage_audits.get(stage, {}), dict) else {}
            text_bits = []
            for value in out.values():
                if isinstance(value, str):
                    text_bits.append(value)
            tokens_out = _approx_tokens(" ".join(text_bits))
            token_budget = int(pack.get("token_budget", 0) or 0)
            included = [str(x).strip() for x in pack.get("included_memory", []) if str(x).strip()]
            memory_ids = [x for x in included if x.startswith("mem_")]
            stage_score = 1.0 if bool(audit.get("ok", False)) else 0.35

            rows.append(
                {
                    "role": str(pack.get("specialist_role", stage)).strip() or stage,
                    "stage": str(stage),
                    "context_pack_id": str(pack.get("context_pack_id", "")).strip(),
                    "cag_rows_used": memory_ids,
                    "tokens_in": token_budget,
                    "tokens_out": tokens_out,
                    "latency_ms": int(stage_timings_ms.get(stage, 0) or 0),
                    "output_score": stage_score,
                    "contract_audit": audit,
                }
            )
        return rows

    def record_run(
        self,
        *,
        run_id: str,
        project: str,
        pipeline: str,
        model: str,
        stages: list[dict[str, Any]],
        final_score: float,
        auditor_findings: list[str],
        promoted_memories: list[str],
        started_at: str,
        finished_at: str,
    ) -> dict[str, Any]:
        payload = {
            "run_id": str(run_id),
            "project": str(project),
            "pipeline": str(pipeline),
            "model": str(model),
            "stages": [dict(x) for x in stages],
            "final_score": float(final_score),
            "auditor_findings": [str(x) for x in auditor_findings if str(x).strip()],
            "promoted_memories": [str(x) for x in promoted_memories if str(x).strip()],
            "started_at": str(started_at or ""),
            "finished_at": str(finished_at or _now_iso()),
            "created_at": _now_iso(),
        }
        run_dir = self.root / str(run_id)
        run_dir.mkdir(parents=True, exist_ok=True)
        run_file = run_dir / "trace.json"
        run_file.write_text(json.dumps(payload, indent=2, ensure_ascii=True), encoding="utf-8")

        index_row = {
            "event": "trace_recorded",
            "run_id": str(run_id),
            "project": str(project),
            "pipeline": str(pipeline),
            "final_score": float(final_score),
            "path": str(run_file.relative_to(self.repo_root)),
            "created_at": payload["created_at"],
        }
        with self.events_path.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(index_row, ensure_ascii=True))
            fh.write("\n")
        return payload
