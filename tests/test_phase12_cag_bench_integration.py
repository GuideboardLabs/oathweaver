from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from tests.common import ensure_runtime  # noqa: F401

from benchmarks.cag_bench_adapter import WorkflowBenchmarkEvaluator, build_cag_bench_adapter
from benchmarks.hardware_profiles import profile_by_name
from benchmarks.paths import default_cag_bench_results_root
from cag.memory_store import CAGMemoryStore
from core.context_compiler import ContextCompiler
from core.context_pack import ContextPackStore
from core.kernel_commands import KernelCommandService
from scheduler.resource_budget import ResourceBudgetManager


class _StubOrchestrator:
    def __init__(self, repo_root: Path) -> None:
        self.repo_root = Path(repo_root)
        self.project_slug = "general"
        self.resource_budget_manager = ResourceBudgetManager()

    def set_project(self, slug: str) -> str:
        self.project_slug = slug
        return slug

    def set_project_mode(self, **kwargs):
        return dict(kwargs)

    def project_mode_snapshot(self, project=None):
        return {"project": project or self.project_slug, "mode": "discovery", "target": "auto", "topic_type": "general"}

    def handle_message(self, text: str, history=None, **kwargs):
        details = kwargs.get("details_sink", {}) if isinstance(kwargs.get("details_sink", {}), dict) else {}
        details["pipeline_run"] = {"ok": True}
        return f"reply:{text}"


class Phase12CagBenchIntegrationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory(prefix="phase12_bench_")
        self.repo_root = Path(self.tmp.name)
        ensure_runtime(self.repo_root)
        self.store = CAGMemoryStore(self.repo_root)

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def test_cag_bench_adapter_round_trip_and_retrieve(self) -> None:
        adapter = build_cag_bench_adapter(self.repo_root, project="general")
        imported = adapter.import_rows(
            [
                {
                    "memory_id": "bench_mem_1",
                    "text": "Use scoped continuity terms for retrieval precision.",
                    "memory_type": "decision",
                    "status": "accepted",
                    "tags": ["cag", "retrieval"],
                    "promoted_terms": ["continuity", "scoped"],
                    "continuity_terms": [{"accepted_terms": ["continuity", "scoped"]}],
                    "project": "general",
                }
            ],
            project="general",
            scope_level="project",
        )
        self.assertEqual(len(imported), 1)

        exported = adapter.export_rows(project="general", limit=20)
        self.assertTrue(exported)
        self.assertEqual(exported[0].get("memory_id"), "bench_mem_1")

        retrieved = adapter.retrieve_scoped(
            task={
                "title": "Need scoped continuity retrieval",
                "prompt": "continuity scoped retrieval",
                "tags": ["retrieval"],
                "continuity_terms": [{"accepted_terms": ["continuity", "scoped"]}],
            },
            project="general",
            k=5,
            return_scores=False,
        )
        self.assertTrue(retrieved)

    def test_workflow_benchmark_gate_and_budget(self) -> None:
        results_root = self.repo_root / "bench_results"
        run_dir = results_root / "run_eval_1"
        run_dir.mkdir(parents=True, exist_ok=True)
        (run_dir / "summary.csv").write_text(
            "trial,status,mode,score,continuity_recall,memory_usage_rate,max_stage_context_tokens\n"
            "1,ok,cag_scoped_promptonly,61,58,64,1700\n"
            "1,ok,8b_oathweaver_plus_cag,63,60,65,1780\n"
            "1,ok,8b_rag,51,42,12,1600\n",
            encoding="utf-8",
        )

        evaluator = WorkflowBenchmarkEvaluator(results_root)
        out = evaluator.evaluate_run(run_id="run_eval_1", hardware_profile_name="8gb_vram_16gb_ram")
        self.assertTrue(out.get("ok"))
        ship_gate = out.get("ship_gate", {})
        self.assertTrue(ship_gate.get("passed"))
        self.assertTrue(ship_gate.get("within_budget"))

    def test_hardware_profile_is_respected_by_budget_paths(self) -> None:
        profile = profile_by_name("8gb_vram_16gb_ram")
        rb = ResourceBudgetManager(profile=profile.to_scheduler_profile())
        self.assertEqual(rb.stage_context_budget(), 1800)
        self.assertEqual(rb.profile.max_context_tokens, 4096)
        self.assertEqual(rb.prefetch_depths(), (1, 1))

        compiler = ContextCompiler(context_pack_store=ContextPackStore(self.repo_root))
        self.assertEqual(compiler._resolve_budget(profile.max_stage_context_tokens), 1800)  # noqa: SLF001

    def test_kernel_service_phase12_benchmark_commands(self) -> None:
        self.store.add_row(
            {
                "text": "Benchmark implication: scoped retrieval improved continuity.",
                "scope": "",
                "scope_level": "project",
                "domain": "computer_science",
                "topic": "programming",
                "thread": "thread_general",
                "project": "general",
                "run": "run_a",
                "type": "benchmark_implication",
                "status": "benchmark-derived",
                "source": "test",
                "validation": {"task_metadata": True, "has_citation": True, "auditor_approved": True, "user_accepted": False, "tests_passed": False, "benchmark_backed": True},
            }
        )

        svc = KernelCommandService(self.repo_root, orchestrator=_StubOrchestrator(self.repo_root), memory_store=self.store)

        results_root = self.repo_root / "bench_results"
        run_dir = results_root / "run_eval_2"
        run_dir.mkdir(parents=True, exist_ok=True)
        (run_dir / "summary.csv").write_text(
            "trial,status,mode,score,continuity_recall,memory_usage_rate,max_stage_context_tokens\n"
            "1,ok,cag_scoped_promptonly,59,55,62,1750\n"
            "1,ok,8b_oathweaver_plus_cag,60,56,64,1790\n",
            encoding="utf-8",
        )
        svc.benchmark_import.results_root = results_root

        exported = svc.benchmark_backend_export(project="general", limit=50)
        self.assertTrue(exported.get("ok"))
        self.assertGreaterEqual(int(exported.get("row_count", 0)), 1)

        workflow = svc.benchmark_workflow_eval(run_id="run_eval_2", hardware_profile="8gb_vram_16gb_ram")
        self.assertTrue(workflow.get("ok"))

        profile_result = svc.apply_hardware_profile(profile_name="8gb_vram_16gb_ram")
        self.assertTrue(profile_result.get("ok"))
        self.assertEqual(str(profile_result.get("profile", {}).get("name", "")), "8gb_vram_16gb_ram")

    def test_default_benchmark_results_root_is_repo_local(self) -> None:
        svc = KernelCommandService(self.repo_root, orchestrator=_StubOrchestrator(self.repo_root), memory_store=self.store)
        expected = default_cag_bench_results_root(self.repo_root)
        self.assertEqual(svc.benchmark_import.results_root, expected)
        self.assertIn(str(self.repo_root), str(svc.benchmark_import.results_root))


if __name__ == "__main__":
    unittest.main()
