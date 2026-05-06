from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from tests.common import ensure_runtime  # noqa: F401

from auditor.benchmark_import import BenchmarkImport
from cag.memory_store import CAGMemoryStore
from core.kernel_commands import KernelCommandService
from interfaces.cli.main import build_parser
from interfaces.tui.command_router import TUICommandRouter


class _StubKernelStore:
    def snapshot(self, project: str) -> dict:
        return {
            "knowledge_spine": {
                "domain": "computer_science",
                "topic": "programming",
                "thread": f"thread_{project}",
                "project": project,
                "run": "run_stub",
            },
            "current_scope": {
                "domain": "computer_science",
                "topic": "programming",
                "thread": f"thread_{project}",
                "project": project,
                "run": "run_stub",
                "scope_level": "run",
                "scope": f"computer_science/programming/thread_{project}/{project}/run_stub",
            },
        }


class _StubWatchtower:
    def scan_project_gaps(self, *, project: str, project_kernel: dict | None = None, auditor_report: dict | None = None) -> dict:
        return {
            "project": project,
            "queued_count": 1,
            "queued_cards": [
                {
                    "id": "card_1",
                    "card_type": "knowledge_gap_card",
                    "status": "queued",
                    "scope_level": "topic",
                }
            ],
        }


class _StubOrchestrator:
    def __init__(self) -> None:
        self.project_slug = "general"
        self.project_kernel_store = _StubKernelStore()
        self.watchtower = _StubWatchtower()

    def set_project(self, slug: str) -> str:
        self.project_slug = slug
        return slug

    def set_project_mode(self, *, mode: str = "", target: str = "", topic_type: str = "", project: str = "") -> dict:
        return {
            "project": project or self.project_slug,
            "mode": mode,
            "target": target,
            "topic_type": topic_type,
        }

    def project_mode_snapshot(self, project: str | None = None) -> dict:
        return {
            "project": project or self.project_slug,
            "mode": "discovery",
            "target": "auto",
            "topic_type": "general",
        }

    def handle_message(self, text: str, history=None, *, thread_id: str = "", force_research: bool = False, force_make: bool = False, details_sink=None, **_: dict) -> str:
        if isinstance(details_sink, dict):
            details_sink["trace_ledger"] = {"run_id": "run_stub", "pipeline": "research_pipeline"}
            details_sink["auditor_report"] = {"run_id": "run_stub", "typed_findings": ["wrong memory scope"]}
            details_sink["watchtower_scan"] = {"queued_count": 1}
        return f"reply:{text}"

    def local_models_text(self) -> str:
        return "- qwen3:8b\n- llama3.1:8b"


class Phase10InterfaceUnificationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory(prefix="phase10_interfaces_")
        self.repo_root = Path(self.tmp.name)
        ensure_runtime(self.repo_root)
        self.memory_store = CAGMemoryStore(self.repo_root)
        self.memory_store.add_row(
            {
                "text": "Use scoped memory rows for continuity improvements.",
                "scope": "computer_science/programming/thread_general/general/run_stub",
                "scope_level": "run",
                "domain": "computer_science",
                "topic": "programming",
                "thread": "thread_general",
                "project": "general",
                "run": "run_stub",
                "type": "decision",
                "status": "accepted",
                "source": "test",
                "validation": {"task_metadata": True, "has_citation": False, "auditor_approved": False, "user_accepted": False, "tests_passed": False, "benchmark_backed": False},
            }
        )
        self.service = KernelCommandService(
            self.repo_root,
            orchestrator=_StubOrchestrator(),
            memory_store=self.memory_store,
        )

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def test_kernel_commands_cover_required_phase10_surface(self) -> None:
        opened = self.service.project_open(project="alpha", mode="discovery", target="report", topic_type="programming")
        self.assertTrue(opened.get("ok"))
        self.assertEqual(opened.get("project"), "alpha")

        run = self.service.pipeline_run(text="Draft a scoped CAG plan")
        self.assertTrue(run.get("ok"))
        self.assertIn("reply:Draft a scoped CAG plan", str(run.get("reply", "")))

        mem = self.service.memory_inspect(project="general", limit=10)
        self.assertTrue(mem.get("ok"))
        self.assertGreaterEqual(int(mem.get("count", 0)), 1)

    def test_benchmark_compare_works_from_results_dirs(self) -> None:
        results_root = self.repo_root / "bench_results"
        run_a = results_root / "run_a"
        run_b = results_root / "run_b"
        run_a.mkdir(parents=True, exist_ok=True)
        run_b.mkdir(parents=True, exist_ok=True)
        (run_a / "summary.csv").write_text(
            "trial,status,mode,score,continuity_recall,memory_usage_rate,memory_recall,memory_precision\n"
            "1,ok,cag,30,20,80,100,50\n",
            encoding="utf-8",
        )
        (run_b / "summary.csv").write_text(
            "trial,status,mode,score,continuity_recall,memory_usage_rate,memory_recall,memory_precision\n"
            "1,ok,cag,45,38,70,100,55\n",
            encoding="utf-8",
        )
        self.service.benchmark_import = BenchmarkImport(results_root)
        result = self.service.benchmark_compare(left_run="run_a", right_run="run_b")
        self.assertTrue(result.get("ok"))
        delta = result.get("delta", {})
        self.assertGreater(float(delta.get("score", 0.0) or 0.0), 0.0)

    def test_tui_router_calls_kernel_commands(self) -> None:
        router = TUICommandRouter(self.repo_root)
        router.kernel = self.service
        out = router.dispatch("/open beta discovery report programming")
        self.assertFalse(out.error)
        payload = json.loads(out.text)
        self.assertEqual(payload.get("project"), "beta")

        out2 = router.dispatch("/watchtower beta")
        self.assertFalse(out2.error)
        payload2 = json.loads(out2.text)
        self.assertTrue(payload2.get("ok"))

    def test_cli_parser_includes_phase10_scriptable_commands(self) -> None:
        parser = build_parser()
        names = sorted(parser._subparsers._group_actions[0].choices.keys())  # type: ignore[attr-defined]
        for expected in [
            "project-open",
            "pipeline-run",
            "memory-inspect",
            "audit-report",
            "watchtower-scan",
            "benchmark-compare",
            "stage-resume",
        ]:
            self.assertIn(expected, names)

    def test_stage_resume_uses_replay_turn(self) -> None:
        with patch("core.kernel_commands.service.replay_turn", return_value={"ok": True, "replay_id": "r1"}) as mocked:
            out = self.service.stage_resume(thread_id="thread_1", from_node="compose", mutate={"foo": "bar"})
        self.assertTrue(out.get("ok"))
        mocked.assert_called_once()


if __name__ == "__main__":
    unittest.main()
