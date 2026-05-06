from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from tests.common import ensure_runtime  # noqa: F401
from auditor import AuditorEngine, BenchmarkImport, RegressionReporter
from auditor.trace_analysis import TraceAnalyzer


class _StubBenchmarkImport(BenchmarkImport):
    def __init__(self) -> None:
        super().__init__(Path("/tmp/does-not-matter"))

    def latest_snapshot(self) -> dict:
        return {
            "available": True,
            "run_id": "bench_run",
            "mode_metrics": {
                "cag": {
                    "score": 38.0,
                    "continuity_recall": 31.0,
                    "memory_usage_rate": 82.0,
                }
            },
            "signals": {
                "score": 38.0,
                "continuity_recall": 31.0,
                "memory_usage_rate": 82.0,
                "high_memory_low_continuity": True,
                "high_memory_low_score": True,
            },
        }


class Phase8AuditorLoopTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory(prefix="phase8_auditor_")
        self.repo_root = Path(self.tmp.name)
        ensure_runtime(self.repo_root)

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def test_benchmark_import_reads_summary_csv_fallback(self) -> None:
        results_dir = self.repo_root / "results" / "run_a"
        results_dir.mkdir(parents=True, exist_ok=True)
        summary = results_dir / "summary.csv"
        summary.write_text(
            "trial,status,mode,score,continuity_recall,memory_usage_rate,memory_recall,memory_precision\n"
            "1,ok,cag,40,30,85,100,50\n"
            "1,ok,cag_scoped,45,55,60,90,55\n",
            encoding="utf-8",
        )
        importer = BenchmarkImport(self.repo_root / "results")
        snapshot = importer.latest_snapshot()
        self.assertTrue(snapshot.get("available", False))
        self.assertEqual(snapshot.get("run_id"), "run_a")
        self.assertTrue(snapshot.get("signals", {}).get("high_memory_low_continuity", False))

    def test_trace_analyzer_produces_typed_findings(self) -> None:
        analyzer = TraceAnalyzer()
        findings = analyzer.analyze(
            trace_row={
                "pipeline": "research_pipeline",
                "stages": [
                    {
                        "role": "planner",
                        "cag_rows_used": ["mem_1", "mem_2", "mem_3", "mem_4", "mem_5", "mem_6", "mem_7", "mem_8", "mem_9"],
                        "contract_audit": {"ok": False},
                    }
                ],
            },
            replay_row={
                "input_payload": {"topic_type": "programming", "target": "cli_tool", "query_mode": "domain_focused"},
                "stage_outputs": {
                    "cag_promotion_gate": {
                        "contradictions": [{"label": "error"}],
                    }
                },
            },
            benchmark_snapshot={
                "signals": {
                    "score": 35.0,
                    "continuity_recall": 20.0,
                    "memory_usage_rate": 82.0,
                    "high_memory_low_continuity": True,
                    "high_memory_low_score": True,
                }
            },
            project_kernel={
                "knowledge_spine": {"domain": "computer_science", "topic": "programming"},
                "execution_spine": {"make_type": "model_runtime_system", "research_focus": "implementation_focused"},
            },
        )
        found_types = {str(x.get("type", "")) for x in findings if isinstance(x, dict)}
        self.assertIn("wrong memory scope", found_types)
        self.assertIn("project memory overfit", found_types)
        self.assertIn("missing topic knowledge", found_types)
        self.assertIn("thread memory contradiction", found_types)

    def test_auditor_engine_and_regression_reporter(self) -> None:
        engine = AuditorEngine(benchmark_import=_StubBenchmarkImport())
        trace_row = {
            "run_id": "run_1",
            "pipeline": "research_pipeline",
            "final_score": 42.0,
            "stages": [
                {
                    "role": "researcher",
                    "cag_rows_used": ["mem_1", "mem_2"],
                    "contract_audit": {"ok": True},
                },
                {
                    "role": "synthesizer",
                    "cag_rows_used": ["mem_3"],
                    "contract_audit": {"ok": True},
                },
            ],
        }
        replay_row = {
            "input_payload": {"topic_type": "programming", "target": "model_runtime_system", "query_mode": "implementation_focused"},
            "stage_outputs": {"cag_promotion_gate": {"contradictions": []}},
        }
        kernel = {
            "knowledge_spine": {"domain": "programming", "topic": "programming"},
            "execution_spine": {"make_type": "model_runtime_system", "research_focus": "implementation_focused"},
        }

        report = engine.audit_run(trace_row=trace_row, replay_row=replay_row, project_kernel=kernel)
        self.assertTrue(report.get("typed_findings"))
        self.assertTrue(report.get("proposed_system_changes"))
        self.assertTrue(report.get("promotion_candidates"))

        reporter = RegressionReporter(self.repo_root)
        written = reporter.write_report(report)
        self.assertEqual(written.get("run_id"), "run_1")
        report_path = self.repo_root / "Runtime" / "auditor" / "regression_reports" / "run_1" / "report.json"
        self.assertTrue(report_path.exists())


if __name__ == "__main__":
    unittest.main()
