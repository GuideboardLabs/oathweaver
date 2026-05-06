from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from tests.common import ROOT, ensure_runtime  # noqa: F401
from core.pipeline_engine import PipelineEngine, pipeline_spec_for_name
from core.state_store import StateStore


class Phase2PipelineEngineTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory(prefix="phase2_pipeline_engine_")
        self.repo_root = Path(self.tmp.name)
        ensure_runtime(self.repo_root)
        self.store = StateStore(self.repo_root)
        self.engine = PipelineEngine(state_store=self.store)

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def test_research_pipeline_executes_all_stages_and_persists_state(self) -> None:
        spec = pipeline_spec_for_name("research_pipeline")
        assert spec is not None

        def runner(stage: str, _stage_state: dict, payload: dict) -> dict:
            if stage == "intake":
                return {"question": payload["text"], "project": payload["project_slug"]}
            if stage == "domain_framing":
                return {"domain": "general_research", "topic": "general", "thread": "thread_general"}
            if stage == "source_discovery":
                return {"web_context": "none"}
            if stage == "evidence_analysis":
                return {"evidence_summary": "ok"}
            if stage == "nuance_pass":
                return {"open_risks": []}
            if stage == "synthesis":
                return {"reply": "done"}
            if stage == "cag_promotion_gate":
                return {"promotion_candidates": []}
            return {}

        result = self.engine.execute(
            spec=spec,
            input_payload={
                "text": "hello",
                "project_slug": "general",
                "topic_type": "general",
                "lane": "research",
            },
            stage_runner=runner,
        )
        self.assertTrue(result.get("ok", False))
        self.assertEqual(result.get("final_output", {}).get("reply"), "done")
        latest = self.store.latest_run_state(str(result.get("run_id", "")))
        self.assertEqual(str(latest.get("run_id", "")).strip(), str(result.get("run_id", "")).strip())

    def test_contract_violation_marks_run_not_ok(self) -> None:
        spec = pipeline_spec_for_name("research_pipeline")
        assert spec is not None

        def runner(stage: str, _stage_state: dict, payload: dict) -> dict:
            if stage == "intake":
                return {"question": payload["text"], "project": payload["project_slug"]}
            if stage == "domain_framing":
                return {"domain": "general_research", "topic": "general", "thread": "thread_general"}
            if stage == "source_discovery":
                return {"web_context": "none"}
            if stage == "evidence_analysis":
                return {"evidence_summary": "ok"}
            if stage == "nuance_pass":
                return {"open_risks": []}
            if stage == "synthesis":
                return {"reply": ""}  # violates must_include reply
            if stage == "cag_promotion_gate":
                return {"promotion_candidates": []}
            return {}

        result = self.engine.execute(
            spec=spec,
            input_payload={
                "text": "hello",
                "project_slug": "general",
                "topic_type": "general",
                "lane": "research",
            },
            stage_runner=runner,
        )
        self.assertFalse(result.get("ok", True))

    def test_canonical_contract_names_still_feed_legacy_stage_keys(self) -> None:
        spec = pipeline_spec_for_name("research_pipeline")
        assert spec is not None

        seen: dict[str, str] = {}

        def runner(stage: str, _stage_state: dict, payload: dict) -> dict:
            if stage == "intake":
                seen["topic_type"] = str(payload.get("topic_type", ""))
                seen["lane"] = str(payload.get("lane", ""))
                return {"question": payload["text"], "project": payload["project_slug"]}
            if stage == "domain_framing":
                return {"domain": "general_research", "topic": "general", "thread": "thread_general"}
            if stage == "source_discovery":
                return {"web_context": "none"}
            if stage == "evidence_analysis":
                return {"evidence_summary": "ok"}
            if stage == "nuance_pass":
                return {"open_risks": []}
            if stage == "synthesis":
                return {"reply": "done"}
            if stage == "cag_promotion_gate":
                return {"promotion_candidates": []}
            return {}

        result = self.engine.execute(
            spec=spec,
            input_payload={
                "text": "hello",
                "project_slug": "general",
                "domain": "general_research",
                "pipeline": "research_pipeline",
            },
            stage_runner=runner,
        )
        self.assertTrue(result.get("ok", False))
        self.assertEqual(seen.get("topic_type"), "general_research")
        self.assertEqual(seen.get("lane"), "research")


if __name__ == "__main__":
    unittest.main()
