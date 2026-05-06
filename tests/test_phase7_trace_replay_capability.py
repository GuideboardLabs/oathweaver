from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from tests.common import ensure_runtime  # noqa: F401
from core.capability_registry import CapabilityRegistry
from core.pipeline_engine import PipelineEngine, pipeline_spec_for_name
from core.replay import ReplayStore
from core.state_store import StateStore
from core.trace_ledger import TraceLedger


class Phase7TraceReplayCapabilityTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory(prefix="phase7_trace_replay_")
        self.repo_root = Path(self.tmp.name)
        ensure_runtime(self.repo_root)

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def test_pipeline_engine_emits_stage_audits_and_timings(self) -> None:
        spec = pipeline_spec_for_name("research_pipeline")
        assert spec is not None
        engine = PipelineEngine(state_store=StateStore(self.repo_root))

        def context_builder(stage: str, _state: dict, _payload: dict, run_id: str, pipeline: str) -> dict:
            return {
                "context_pack_id": f"ctx_{stage}",
                "run_id": run_id,
                "pipeline": pipeline,
                "stage": stage,
                "specialist_role": stage,
                "project": "proj",
                "domain": "general",
                "topic": "general",
                "thread": "thread_proj",
                "token_budget": 1800,
                "output_contract": stage,
                "included_memory": ["mem_1"],
                "excluded_memory_reasoning": [],
                "memory_snippets": [{"id": "mem_1", "kind": "memory", "text": "x"}],
                "retrieval_results": {},
                "benchmark_lessons": [],
                "few_shot_examples": [],
                "created_at": "2026-01-01T00:00:00+00:00",
            }

        def runner(stage: str, _stage_state: dict, payload: dict) -> dict:
            self.assertIn("context_pack", payload)
            if stage == "intake":
                return {"question": payload["text"], "project": payload["project_slug"]}
            if stage == "domain_framing":
                return {"domain": "general", "topic": "general", "thread": "thread_proj"}
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

        result = engine.execute(
            spec=spec,
            input_payload={
                "text": "hello",
                "project_slug": "proj",
                "topic_type": "general",
                "lane": "research",
            },
            stage_runner=runner,
            context_pack_builder=context_builder,
        )
        self.assertTrue(result["ok"])
        self.assertEqual(len(result.get("stage_audits", {})), len(spec.stages))
        self.assertEqual(len(result.get("stage_timings_ms", {})), len(spec.stages))
        self.assertTrue(str(result.get("started_at", "")).strip())
        self.assertTrue(str(result.get("finished_at", "")).strip())

    def test_trace_ledger_and_replay_store_persist_run_artifacts(self) -> None:
        ledger = TraceLedger(self.repo_root)
        replay = ReplayStore(self.repo_root)

        stage_rows = ledger.build_stage_rows(
            stage_outputs={
                "synthesis": {"reply": "done"},
                "cag_promotion_gate": {"promotion_candidates": [], "accepted_memory_ids": ["mem_22"]},
            },
            context_packs={
                "synthesis": {
                    "context_pack_id": "ctx_syn",
                    "specialist_role": "synthesizer",
                    "token_budget": 1600,
                    "included_memory": ["mem_22", "dl_1"],
                },
                "cag_promotion_gate": {
                    "context_pack_id": "ctx_gate",
                    "specialist_role": "memory_critic",
                    "token_budget": 1200,
                    "included_memory": ["mem_22"],
                },
            },
            stage_timings_ms={"synthesis": 1200, "cag_promotion_gate": 300},
            stage_audits={
                "synthesis": {"ok": True, "missing_fields": [], "forbidden_fields": []},
                "cag_promotion_gate": {"ok": True, "missing_fields": [], "forbidden_fields": []},
            },
        )
        self.assertEqual(len(stage_rows), 2)

        trace = ledger.record_run(
            run_id="run_1",
            project="proj",
            pipeline="research_pipeline",
            model="test-model",
            stages=stage_rows,
            final_score=0.88,
            auditor_findings=[],
            promoted_memories=["mem_22"],
            started_at="2026-01-01T00:00:00+00:00",
            finished_at="2026-01-01T00:00:05+00:00",
        )
        self.assertEqual(trace["run_id"], "run_1")

        bundle = replay.save_bundle(
            run_id="run_1",
            project="proj",
            pipeline="research_pipeline",
            model_settings={"model": "test-model"},
            input_payload={"text": "hello"},
            context_packs={"synthesis": {"context_pack_id": "ctx_syn"}},
            stage_outputs={"synthesis": {"reply": "done"}},
            stage_audits={"synthesis": {"ok": True}},
            stage_timings_ms={"synthesis": 1200},
            hardware_profile={"name": "8gb_vram_16gb_ram"},
            promoted_memory_ids=["mem_22"],
            started_at="2026-01-01T00:00:00+00:00",
            finished_at="2026-01-01T00:00:05+00:00",
        )
        self.assertEqual(bundle["run_id"], "run_1")
        loaded = replay.load_bundle("run_1")
        self.assertEqual(loaded.get("run_id"), "run_1")

    def test_capability_registry_seeds_default_and_records_observations(self) -> None:
        registry = CapabilityRegistry(self.repo_root)
        claims = registry.list_claims()
        self.assertTrue(any("70B quality" in str(row.get("claim", "")) for row in claims))

        updated = registry.record_run_observation(
            claim_text="8B + CAG + pipeline can approach 70B quality on long-running architecture work",
            run_id="run_xyz",
            pipeline="research_pipeline",
            final_score=0.79,
            benchmark_id="cag_long_project_v3",
            status="hypothesis",
        )
        observations = updated.get("observations", []) if isinstance(updated.get("observations", []), list) else []
        self.assertTrue(any(str(row.get("run_id", "")) == "run_xyz" for row in observations if isinstance(row, dict)))


if __name__ == "__main__":
    unittest.main()
