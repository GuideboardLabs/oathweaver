from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from auditor.benchmark_import import BenchmarkImport
from benchmarks.cag_bench_adapter import WorkflowBenchmarkEvaluator, build_cag_bench_adapter
from benchmarks.hardware_profiles import profile_by_name
from benchmarks.paths import default_cag_bench_results_root
from cag.memory_store import CAGMemoryStore
from orchestrator.main import OathweaverOrchestrator
from orchestrator.pipelines import replay_turn


class KernelCommandService:
    """Unified command surface shared by GUI/TUI/CLI/API interfaces."""

    def __init__(
        self,
        repo_root: Path,
        *,
        orchestrator: OathweaverOrchestrator | None = None,
        memory_store: CAGMemoryStore | None = None,
    ) -> None:
        self.repo_root = Path(repo_root)
        self.orchestrator = orchestrator or OathweaverOrchestrator(self.repo_root)
        self.memory_store = memory_store or CAGMemoryStore(self.repo_root)
        self.benchmark_import = BenchmarkImport(default_cag_bench_results_root(self.repo_root))

    # ------------------------------------------------------------------
    # Kernel commands exposed to every interface
    # ------------------------------------------------------------------

    def project_open(
        self,
        *,
        project: str,
        mode: str = "",
        target: str = "",
        topic_type: str = "",
    ) -> dict[str, Any]:
        project_slug = str(project or "").strip() or "general"
        self.orchestrator.set_project(project_slug)
        if mode or target or topic_type:
            self.orchestrator.set_project_mode(
                mode=str(mode or ""),
                target=str(target or ""),
                topic_type=str(topic_type or ""),
                project=project_slug,
            )
        snapshot = self.orchestrator.project_mode_snapshot(project_slug)
        kernel = self.orchestrator.project_kernel_store.snapshot(project_slug)
        return {
            "ok": True,
            "project": project_slug,
            "project_mode": snapshot,
            "project_kernel": kernel,
        }

    def pipeline_run(
        self,
        *,
        text: str,
        history: list[dict[str, str]] | None = None,
        thread_id: str = "",
        force_research: bool = False,
        force_make: bool = False,
        hardware_profile: str = "",
    ) -> dict[str, Any]:
        profile_row: dict[str, Any] = {}
        if hardware_profile.strip():
            profile_result = self.apply_hardware_profile(profile_name=hardware_profile)
            profile_row = dict(profile_result.get("profile", {})) if isinstance(profile_result.get("profile", {}), dict) else {}
        details: dict[str, Any] = {}
        reply = self.orchestrator.handle_message(
            str(text or ""),
            history=list(history or []),
            thread_id=str(thread_id or ""),
            force_research=bool(force_research),
            force_make=bool(force_make),
            details_sink=details,
        )
        return {
            "ok": True,
            "reply": str(reply or ""),
            "project": str(self.orchestrator.project_slug),
            "pipeline_run": dict(details.get("pipeline_run", {})) if isinstance(details.get("pipeline_run", {}), dict) else {},
            "trace_ledger": dict(details.get("trace_ledger", {})) if isinstance(details.get("trace_ledger", {}), dict) else {},
            "replay_bundle": dict(details.get("replay_bundle", {})) if isinstance(details.get("replay_bundle", {}), dict) else {},
            "auditor_report": dict(details.get("auditor_report", {})) if isinstance(details.get("auditor_report", {}), dict) else {},
            "watchtower_scan": dict(details.get("watchtower_scan", {})) if isinstance(details.get("watchtower_scan", {}), dict) else {},
            "hardware_profile": profile_row,
        }

    def memory_inspect(self, *, project: str = "", limit: int = 40) -> dict[str, Any]:
        target_project = str(project or self.orchestrator.project_slug).strip() or "general"
        rows = self.memory_store.list_rows(
            project=target_project,
            include_expired=True,
            include_superseded=True,
            limit=max(1, int(limit)),
        )
        preview = []
        for row in rows:
            preview.append(
                {
                    "memory_id": str(row.get("memory_id", "")).strip(),
                    "type": str(row.get("type", "")).strip(),
                    "status": str(row.get("status", "")).strip(),
                    "scope_level": str(row.get("scope_level", "")).strip(),
                    "project": str(row.get("project", "")).strip(),
                    "text": str(row.get("text", "")).strip()[:220],
                    "updated_at": str(row.get("updated_at", "")).strip(),
                }
            )
        return {
            "ok": True,
            "project": target_project,
            "count": len(preview),
            "rows": preview,
        }

    def audit_report(self, *, run_id: str = "") -> dict[str, Any]:
        root = self.repo_root / "Runtime" / "auditor" / "regression_reports"
        index_path = root / "reports.jsonl"
        if run_id.strip():
            report_path = root / run_id.strip() / "report.json"
            if not report_path.exists():
                return {"ok": False, "error": f"Audit report not found for run_id={run_id.strip()}"}
            return {"ok": True, "report": self._load_json(report_path), "path": str(report_path)}

        if not index_path.exists():
            return {"ok": False, "error": "No audit report index found."}
        rows = self._read_jsonl(index_path)
        if not rows:
            return {"ok": False, "error": "No audit reports recorded yet."}
        latest = rows[-1]
        report_rel = str(latest.get("path", "")).strip()
        report_path = self.repo_root / report_rel if report_rel else Path("")
        report = self._load_json(report_path) if report_rel and report_path.exists() else {}
        return {
            "ok": True,
            "latest_index": latest,
            "report": report,
            "path": str(report_path) if report_rel else "",
        }

    def watchtower_scan(self, *, project: str = "") -> dict[str, Any]:
        target_project = str(project or self.orchestrator.project_slug).strip() or "general"
        kernel = self.orchestrator.project_kernel_store.snapshot(target_project)
        report_resp = self.audit_report()
        report = dict(report_resp.get("report", {})) if isinstance(report_resp.get("report", {}), dict) else {}
        scan = self.orchestrator.watchtower.scan_project_gaps(
            project=target_project,
            project_kernel=kernel,
            auditor_report=report,
        )
        return {
            "ok": True,
            "project": target_project,
            "scan": scan,
        }

    def benchmark_compare(self, *, left_run: str = "", right_run: str = "") -> dict[str, Any]:
        if left_run.strip() and right_run.strip():
            left = self._benchmark_snapshot_for_run(left_run.strip())
            right = self._benchmark_snapshot_for_run(right_run.strip())
        else:
            latest = self._latest_benchmark_runs(limit=2)
            if len(latest) < 2:
                return {
                    "ok": False,
                    "error": f"Need at least two benchmark runs in {self.benchmark_import.results_root}",
                }
            left = self._benchmark_snapshot_for_run(latest[1])
            right = self._benchmark_snapshot_for_run(latest[0])

        left_signals = left.get("signals", {}) if isinstance(left.get("signals", {}), dict) else {}
        right_signals = right.get("signals", {}) if isinstance(right.get("signals", {}), dict) else {}
        delta = {
            "score": float(right_signals.get("score", 0.0) or 0.0) - float(left_signals.get("score", 0.0) or 0.0),
            "continuity_recall": float(right_signals.get("continuity_recall", 0.0) or 0.0)
            - float(left_signals.get("continuity_recall", 0.0) or 0.0),
            "memory_usage_rate": float(right_signals.get("memory_usage_rate", 0.0) or 0.0)
            - float(left_signals.get("memory_usage_rate", 0.0) or 0.0),
        }
        return {
            "ok": True,
            "left": left,
            "right": right,
            "delta": delta,
            "summary": self._benchmark_delta_summary(delta),
        }

    def benchmark_backend_export(
        self,
        *,
        project: str = "",
        limit: int = 500,
    ) -> dict[str, Any]:
        target_project = str(project or self.orchestrator.project_slug).strip() or "general"
        adapter = build_cag_bench_adapter(self.repo_root, project=target_project)
        rows = adapter.export_rows(project=target_project, limit=max(1, int(limit)))
        return {
            "ok": True,
            "project": target_project,
            "backend_name": "oathweaver_cag_memory_store",
            "row_count": len(rows),
            "rows": rows,
        }

    def benchmark_workflow_eval(
        self,
        *,
        run_id: str = "",
        hardware_profile: str = "8gb_vram_16gb_ram",
    ) -> dict[str, Any]:
        evaluator = WorkflowBenchmarkEvaluator(self.benchmark_import.results_root)
        target_run = str(run_id or "").strip()
        if not target_run:
            latest = self._latest_benchmark_runs(limit=1)
            if not latest:
                return {"ok": False, "error": "No benchmark runs found."}
            target_run = latest[0]
        return evaluator.evaluate_run(run_id=target_run, hardware_profile_name=hardware_profile)

    def apply_hardware_profile(self, *, profile_name: str = "8gb_vram_16gb_ram") -> dict[str, Any]:
        profile = profile_by_name(profile_name)
        # Phase-12 guarantee: scheduler and context budget honor benchmark profile.
        if hasattr(self.orchestrator, "resource_budget_manager"):
            self.orchestrator.resource_budget_manager.profile = profile.to_scheduler_profile()
        return {"ok": True, "profile": profile.as_dict()}

    def stage_resume(
        self,
        *,
        thread_id: str,
        from_node: str = "",
        mutate: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        result = replay_turn(
            self.orchestrator,
            thread_id=str(thread_id or "").strip(),
            from_node=str(from_node or "").strip(),
            mutate=dict(mutate or {}),
        )
        ok = bool(result.get("ok", False))
        return {
            "ok": ok,
            "replay": result,
        }

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _latest_benchmark_runs(self, *, limit: int = 2) -> list[str]:
        root = self.benchmark_import.results_root
        if not root.exists() or not root.is_dir():
            return []
        dirs = [p for p in root.iterdir() if p.is_dir()]
        dirs.sort(key=lambda p: p.stat().st_mtime, reverse=True)
        return [x.name for x in dirs[: max(1, int(limit))]]

    def _benchmark_snapshot_for_run(self, run_id: str) -> dict[str, Any]:
        run_dir = self.benchmark_import.results_root / str(run_id)
        if not run_dir.exists() or not run_dir.is_dir():
            return {
                "available": False,
                "run_id": str(run_id),
                "reason": "run_dir_not_found",
            }
        runs_jsonl = run_dir / "runs.jsonl"
        if runs_jsonl.exists():
            rows = self.benchmark_import._read_runs_jsonl(runs_jsonl)  # noqa: SLF001
            summary = self.benchmark_import._summarize_rows(rows)  # noqa: SLF001
            summary.update({"available": True, "run_id": str(run_id), "source": str(runs_jsonl)})
            return summary
        summary_csv = run_dir / "summary.csv"
        if summary_csv.exists():
            rows = self.benchmark_import._read_summary_csv(summary_csv)  # noqa: SLF001
            summary = self.benchmark_import._summarize_rows(rows)  # noqa: SLF001
            summary.update({"available": True, "run_id": str(run_id), "source": str(summary_csv)})
            return summary
        aggregated_csv = run_dir / "aggregated_metrics.csv"
        if aggregated_csv.exists():
            modes = self.benchmark_import._read_aggregated_modes(aggregated_csv)  # noqa: SLF001
            return {
                "available": True,
                "run_id": str(run_id),
                "source": str(aggregated_csv),
                "mode_metrics": modes,
                "signals": self.benchmark_import._signals_from_modes(modes),  # noqa: SLF001
            }
        return {
            "available": False,
            "run_id": str(run_id),
            "reason": "no_supported_files",
        }

    @staticmethod
    def _benchmark_delta_summary(delta: dict[str, float]) -> str:
        score = float(delta.get("score", 0.0) or 0.0)
        continuity = float(delta.get("continuity_recall", 0.0) or 0.0)
        memory = float(delta.get("memory_usage_rate", 0.0) or 0.0)
        return (
            f"score_delta={score:+.2f}, continuity_delta={continuity:+.2f}, "
            f"memory_usage_delta={memory:+.2f}"
        )

    @staticmethod
    def _load_json(path: Path) -> dict[str, Any]:
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            return {}
        return dict(payload) if isinstance(payload, dict) else {}

    @staticmethod
    def _read_jsonl(path: Path) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        for line in path.read_text(encoding="utf-8").splitlines():
            text = str(line or "").strip()
            if not text:
                continue
            try:
                row = json.loads(text)
            except Exception:
                continue
            if isinstance(row, dict):
                rows.append(row)
        return rows
