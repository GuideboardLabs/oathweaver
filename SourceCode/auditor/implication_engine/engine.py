from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from auditor.benchmark_import import BenchmarkImport
from auditor.trace_analysis import TraceAnalyzer


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


class AuditorEngine:
    """Typed auditor loop: trace + benchmark signals -> implications + proposals."""

    def __init__(self, *, benchmark_import: BenchmarkImport, trace_analyzer: TraceAnalyzer | None = None) -> None:
        self.benchmark_import = benchmark_import
        self.trace_analyzer = trace_analyzer or TraceAnalyzer()

    def audit_run(
        self,
        *,
        trace_row: dict[str, Any],
        replay_row: dict[str, Any],
        project_kernel: dict[str, Any],
    ) -> dict[str, Any]:
        benchmark_snapshot = self.benchmark_import.latest_snapshot()
        findings = self.trace_analyzer.analyze(
            trace_row=trace_row,
            replay_row=replay_row,
            benchmark_snapshot=benchmark_snapshot,
            project_kernel=project_kernel,
        )
        proposed_system_changes = self._proposals_for_findings(findings)
        promotion_candidates = self._promotion_candidates(findings, benchmark_snapshot, trace_row)
        return {
            "run_id": str(trace_row.get("run_id", "")).strip(),
            "pipeline": str(trace_row.get("pipeline", "")).strip(),
            "typed_findings": [dict(x) for x in findings],
            "proposed_system_changes": proposed_system_changes,
            "promotion_candidates": promotion_candidates,
            "benchmark_snapshot": benchmark_snapshot,
            "created_at": _now_iso(),
        }

    @staticmethod
    def _proposals_for_findings(findings: list[dict[str, Any]]) -> list[str]:
        mapping = {
            "wrong domain": "Tighten Domain Framing stage and enforce domain/topic alignment checks before synthesis.",
            "wrong make type": "Strengthen make-type routing in Project Kernel update and planner stage contracts.",
            "wrong research focus": "Tune research-focus inference and feed corrective hints into Context Compiler profiles.",
            "wrong specialist mix": "Adjust specialist derivation rules and on-deck scheduling manifests for this pipeline.",
            "wrong memory scope": "Reduce memory scope breadth in Context Compiler and prioritize thread-level validated memory.",
            "missing topic knowledge": "Queue Watchtower knowledge-gap card and require more source discovery for this topic.",
            "thread memory contradiction": "Increase contradiction scrutiny at CAG promotion gate and require explicit supersession evidence.",
            "project memory overfit": "Lower memory-usage budget and penalize stale/high-volume memory retrieval in selector tuning.",
        }
        out: list[str] = []
        for row in findings:
            ftype = str(row.get("type", "")).strip()
            proposal = mapping.get(ftype)
            if proposal and proposal not in out:
                out.append(proposal)
        return out

    @staticmethod
    def _promotion_candidates(
        findings: list[dict[str, Any]],
        benchmark_snapshot: dict[str, Any],
        trace_row: dict[str, Any],
    ) -> list[dict[str, Any]]:
        run_id = str(trace_row.get("run_id", "")).strip()
        score = float(trace_row.get("final_score", 0.0) or 0.0)
        signals = benchmark_snapshot.get("signals", {}) if isinstance(benchmark_snapshot.get("signals", {}), dict) else {}
        continuity = float(signals.get("continuity_recall", 0.0) or 0.0)
        memory_usage = float(signals.get("memory_usage_rate", 0.0) or 0.0)
        out: list[dict[str, Any]] = []
        for row in findings:
            ftype = str(row.get("type", "")).strip()
            sev = str(row.get("severity", "low")).strip().lower()
            text = (
                f"Auditor implication ({ftype}) for {run_id}: final_score={score:.2f}, "
                f"continuity_recall={continuity:.2f}, memory_usage_rate={memory_usage:.2f}."
            )
            confidence = 0.72 if sev == "high" else (0.6 if sev == "medium" else 0.5)
            out.append(
                {
                    "text": text,
                    "type": "benchmark_implication",
                    "status": "benchmark-derived",
                    "human_status": "unreviewed",
                    "confidence": confidence,
                    "tags": ["auditor", "benchmark", ftype.replace(" ", "_")],
                    "promoted_terms": [ftype.replace(" ", "_"), "continuity_recall", "memory_usage_rate"],
                    "source": "auditor_implication_engine",
                    "validation": {
                        "benchmark_backed": True,
                        "auditor_approved": True,
                        "task_metadata": True,
                    },
                }
            )
        return out
