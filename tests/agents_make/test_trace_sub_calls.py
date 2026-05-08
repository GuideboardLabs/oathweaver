from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from tests.common import ensure_runtime  # noqa: F401
from core.trace_ledger import TraceLedger


class TraceSubCallsTests(unittest.TestCase):
    def test_patch_stage_sub_calls_are_exposed(self) -> None:
        with tempfile.TemporaryDirectory(prefix="trace_subcalls_") as tmp:
            repo_root = Path(tmp)
            ensure_runtime(repo_root)
            ledger = TraceLedger(repo_root)
            rows = ledger.build_stage_rows(
                stage_outputs={
                    "patch_artifact_generation": {
                        "worker_result": {
                            "llm_calls": [
                                {"label": "spec_generator", "ok": True},
                                {"label": "api_slot", "ok": False},
                            ]
                        }
                    }
                },
                context_packs={"patch_artifact_generation": {"token_budget": 1200, "included_memory": []}},
                stage_timings_ms={"patch_artifact_generation": 200},
                stage_audits={"patch_artifact_generation": {"ok": True}},
            )
            self.assertEqual(len(rows), 1)
            stage = rows[0]
            self.assertEqual(stage["llm_calls_total"], 2)
            self.assertEqual(stage["llm_calls_failed"], 1)
            self.assertEqual(stage["sub_calls"][0]["label"], "spec_generator")

    def test_requirements_stage_llm_sub_calls_are_exposed(self) -> None:
        with tempfile.TemporaryDirectory(prefix="trace_stage_subcalls_") as tmp:
            repo_root = Path(tmp)
            ensure_runtime(repo_root)
            ledger = TraceLedger(repo_root)
            rows = ledger.build_stage_rows(
                stage_outputs={
                    "requirements": {
                        "requirements": {
                            "request": "Build app",
                            "target": "web_app",
                            "lane": "make_app",
                        },
                        "llm_sub_calls": [
                            {"label": "requirements", "ok": False, "error": "no_model_configured"}
                        ],
                    }
                },
                context_packs={"requirements": {"token_budget": 1200, "included_memory": []}},
                stage_timings_ms={"requirements": 4},
                stage_audits={"requirements": {"ok": True}},
            )
            self.assertEqual(len(rows), 1)
            stage = rows[0]
            self.assertEqual(stage["llm_calls_total"], 1)
            self.assertEqual(stage["llm_calls_failed"], 1)
            self.assertEqual(stage["sub_calls"][0]["label"], "requirements")


if __name__ == "__main__":
    unittest.main()
