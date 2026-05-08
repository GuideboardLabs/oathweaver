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


def _collect_text_bits(value: Any) -> list[str]:
    bits: list[str] = []
    if isinstance(value, str):
        text = value.strip()
        if text:
            bits.append(text)
        return bits
    if isinstance(value, dict):
        for item in value.values():
            bits.extend(_collect_text_bits(item))
        return bits
    if isinstance(value, (list, tuple)):
        for item in value:
            bits.extend(_collect_text_bits(item))
        return bits
    return bits


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
            text_bits: list[str] = []
            for value in out.values():
                text_bits.extend(_collect_text_bits(value))
            tokens_out = _approx_tokens(" ".join(text_bits))
            token_budget = int(pack.get("token_budget", 0) or 0)
            included = [str(x).strip() for x in pack.get("included_memory", []) if str(x).strip()]
            memory_ids = [x for x in included if x.startswith("mem_")]
            stage_score = 1.0 if bool(audit.get("ok", False)) else 0.35
            stage_sub_calls: list[dict[str, Any]] = []
            if isinstance(out.get("llm_sub_calls", []), list):
                stage_sub_calls = [dict(item) for item in out.get("llm_sub_calls", []) if isinstance(item, dict)]
            patch_sub_calls: list[dict[str, Any]] = []
            if stage == "patch_artifact_generation":
                worker_result = out.get("worker_result", {}) if isinstance(out.get("worker_result", {}), dict) else {}
                raw_calls = worker_result.get("llm_calls", []) if isinstance(worker_result.get("llm_calls", []), list) else []
                patch_sub_calls = [dict(item) for item in raw_calls if isinstance(item, dict)]
            sub_calls = stage_sub_calls + patch_sub_calls

            row = {
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
            if sub_calls:
                row["sub_calls"] = sub_calls
                row["llm_calls_total"] = len(sub_calls)
                row["llm_calls_failed"] = sum(1 for call in sub_calls if not bool(call.get("ok", False)))
            rows.append(row)
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
