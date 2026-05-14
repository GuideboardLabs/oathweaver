from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from tests.common import ensure_runtime  # noqa: F401
from core.pipeline_engine import PipelineEngine
from core.pipeline_engine.specs import PipelineSpec
from core.state_store import StateStore


class PipelineEngineSpecialistAuditTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory(prefix="pipeline_specialist_audit_")
        self.repo_root = Path(self.tmp.name)
        ensure_runtime(self.repo_root)
        self.engine = PipelineEngine(state_store=StateStore(self.repo_root))

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def test_stage_audit_includes_specialist_manifest_checks(self) -> None:
        spec = PipelineSpec(
            name="unit_pipeline",
            input_contract=("text", "project_slug", "pipeline"),
            stages=("planner",),
            final_stage="planner",
        )

        def _context_builder(stage: str, _stage_state: dict, _payload: dict, run_id: str, pipeline: str) -> dict:
            _ = (stage, run_id, pipeline)
            return {
                "context_pack_id": "ctx_unit",
                "specialist_manifest": {
                    "specialist_role": "planner",
                    "output_schema": "planner_plan_v1",
                    "verifier_rubric": "plan_specificity_and_feasibility_v1",
                },
            }

        def _runner(stage: str, _stage_state: dict, _payload: dict) -> dict:
            self.assertEqual(stage, "planner")
            return {"plan": "Create minimal deterministic patch."}

        result = self.engine.execute(
            spec=spec,
            input_payload={"text": "x", "project_slug": "general", "pipeline": "unit_pipeline"},
            stage_runner=_runner,
            context_pack_builder=_context_builder,
        )
        self.assertTrue(result["ok"])
        planner_audit = result.get("stage_audits", {}).get("planner", {})
        self.assertIn("specialist_audit", planner_audit)
        self.assertTrue(bool(planner_audit.get("specialist_audit", {}).get("ok", False)))


if __name__ == "__main__":
    unittest.main()
