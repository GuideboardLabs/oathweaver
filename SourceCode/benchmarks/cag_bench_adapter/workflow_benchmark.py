from __future__ import annotations

import csv
from pathlib import Path
from typing import Any

from benchmarks.hardware_profiles import BenchmarkHardwareProfile, profile_by_name


_WORKFLOW_MODE_ALIASES: dict[str, list[str]] = {
    "8b_one_shot": ["8b_one_shot", "one_shot_8b", "oneshot_8b", "one_shot"],
    "8b_rag": ["8b_rag", "rag_8b", "rag"],
    "8b_cag": ["8b_cag", "cag_8b", "cag"],
    "8b_oathweaver_multi_agent_no_cag": ["8b_oathweaver_multi_agent_no_cag", "oathweaver_multi_agent_no_cag", "oathweaver_no_cag"],
    "8b_oathweaver_plus_cag": ["8b_oathweaver_plus_cag", "oathweaver_plus_cag", "oathweaver_cag"],
    "70b_one_shot": ["70b_one_shot", "one_shot_70b", "oneshot_70b"],
    "cag_scoped_promptonly": ["cag_scoped_promptonly", "cag_scoped_prompt_only"],
}


class WorkflowBenchmarkEvaluator:
    """Evaluate benchmark run summaries against phase-12 workflow targets."""

    def __init__(self, results_root: Path) -> None:
        self.results_root = Path(results_root)

    def evaluate_run(
        self,
        *,
        run_id: str,
        hardware_profile_name: str = "8gb_vram_16gb_ram",
    ) -> dict[str, Any]:
        run_dir = self.results_root / str(run_id)
        if not run_dir.exists() or not run_dir.is_dir():
            return {"ok": False, "error": f"run not found: {run_id}"}

        rows = self._load_summary_rows(run_dir)
        if not rows:
            return {"ok": False, "error": f"no summary rows for run: {run_id}"}

        profile = profile_by_name(hardware_profile_name)
        by_mode = self._mode_means(rows)
        workflow_scores = self._workflow_scores(by_mode)
        gate = self._ship_gate(workflow_scores)
        budget = self._budget_gate(rows, profile)

        return {
            "ok": True,
            "run_id": run_id,
            "hardware_profile": profile.as_dict(),
            "workflow_scores": workflow_scores,
            "ship_gate": {
                **gate,
                **budget,
                "passed": bool(gate.get("passed", False) and budget.get("within_budget", False)),
            },
        }

    @staticmethod
    def _load_summary_rows(run_dir: Path) -> list[dict[str, Any]]:
        summary_path = run_dir / "summary.csv"
        if not summary_path.exists():
            return []
        with summary_path.open("r", encoding="utf-8") as fh:
            reader = csv.DictReader(fh)
            return [dict(x) for x in reader if isinstance(x, dict)]

    @staticmethod
    def _mode_means(rows: list[dict[str, Any]]) -> dict[str, dict[str, float]]:
        totals: dict[str, dict[str, float]] = {}
        counts: dict[str, int] = {}
        for row in rows:
            mode = str(row.get("mode", "")).strip().lower()
            if not mode:
                continue
            bucket = totals.setdefault(
                mode,
                {
                    "score": 0.0,
                    "continuity_recall": 0.0,
                    "memory_usage_rate": 0.0,
                    "max_stage_context_tokens": 0.0,
                },
            )
            for key in ["score", "continuity_recall", "memory_usage_rate", "max_stage_context_tokens"]:
                try:
                    bucket[key] += float(row.get(key, 0.0) or 0.0)
                except Exception:
                    pass
            counts[mode] = counts.get(mode, 0) + 1

        out: dict[str, dict[str, float]] = {}
        for mode, vals in totals.items():
            n = max(1, counts.get(mode, 1))
            out[mode] = {k: float(v / n) for k, v in vals.items()}
        return out

    @staticmethod
    def _workflow_scores(by_mode: dict[str, dict[str, float]]) -> dict[str, dict[str, Any]]:
        out: dict[str, dict[str, Any]] = {}
        for key, aliases in _WORKFLOW_MODE_ALIASES.items():
            resolved = ""
            metric: dict[str, float] = {}
            for alias in aliases:
                if alias in by_mode:
                    resolved = alias
                    metric = dict(by_mode[alias])
                    break
            out[key] = {
                "mode": resolved,
                "available": bool(resolved),
                "score": float(metric.get("score", 0.0) or 0.0),
                "continuity_recall": float(metric.get("continuity_recall", 0.0) or 0.0),
                "memory_usage_rate": float(metric.get("memory_usage_rate", 0.0) or 0.0),
                "max_stage_context_tokens": float(metric.get("max_stage_context_tokens", 0.0) or 0.0),
            }
        return out

    @staticmethod
    def _ship_gate(workflow_scores: dict[str, dict[str, Any]]) -> dict[str, Any]:
        fox = workflow_scores.get("8b_oathweaver_plus_cag", {}) if isinstance(workflow_scores.get("8b_oathweaver_plus_cag", {}), dict) else {}
        promptonly = workflow_scores.get("cag_scoped_promptonly", {}) if isinstance(workflow_scores.get("cag_scoped_promptonly", {}), dict) else {}
        if not fox.get("available", False) or not promptonly.get("available", False):
            return {
                "passed": False,
                "reason": "required_modes_missing",
                "oathweaver_plus_cag_score": float(fox.get("score", 0.0) or 0.0),
                "cag_scoped_promptonly_score": float(promptonly.get("score", 0.0) or 0.0),
            }

        fox_score = float(fox.get("score", 0.0) or 0.0)
        prompt_score = float(promptonly.get("score", 0.0) or 0.0)
        return {
            "passed": bool(fox_score >= prompt_score),
            "reason": "win_or_tie" if fox_score >= prompt_score else "below_promptonly",
            "oathweaver_plus_cag_score": fox_score,
            "cag_scoped_promptonly_score": prompt_score,
        }

    @staticmethod
    def _budget_gate(rows: list[dict[str, Any]], profile: BenchmarkHardwareProfile) -> dict[str, Any]:
        observed = 0.0
        found = False
        for row in rows:
            for key in ["max_stage_context_tokens", "stage_context_tokens", "context_tokens"]:
                raw = row.get(key)
                if raw is None or str(raw).strip() == "":
                    continue
                try:
                    val = float(raw)
                except Exception:
                    continue
                observed = max(observed, val)
                found = True
        if not found:
            return {
                "within_budget": True,
                "budget_source": "no_context_token_column",
                "observed_max_stage_context_tokens": 0.0,
                "profile_max_stage_context_tokens": float(profile.max_stage_context_tokens),
            }
        return {
            "within_budget": bool(observed <= float(profile.max_stage_context_tokens)),
            "budget_source": "summary_csv",
            "observed_max_stage_context_tokens": float(observed),
            "profile_max_stage_context_tokens": float(profile.max_stage_context_tokens),
        }
