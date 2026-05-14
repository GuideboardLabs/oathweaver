from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from tests.common import ensure_runtime  # noqa: F401
from core.pipeline_engine import PipelineEngine, pipeline_spec_for_name
from core.state_store import StateStore
from scheduler import BenchManager, OnDeckRuntime, ResourceBudgetManager, SpecialistRegistry


class Phase5OnDeckRuntimeTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory(prefix="phase5_on_deck_")
        self.repo_root = Path(self.tmp.name)
        ensure_runtime(self.repo_root)
        self.resource_budget = ResourceBudgetManager()
        self.specialists = SpecialistRegistry()
        self.bench = BenchManager(self.repo_root)
        self.runtime = OnDeckRuntime(
            specialist_registry=self.specialists,
            budget_manager=self.resource_budget,
            bench_manager=self.bench,
        )

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def test_on_deck_runtime_prefetches_next_stage_context_pack(self) -> None:
        spec = pipeline_spec_for_name("research_pipeline")
        assert spec is not None

        def builder(stage: str, _stage_state: dict, _payload: dict, run_id: str, pipeline: str) -> dict:
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
                "included_memory": [],
                "excluded_memory_reasoning": [],
                "memory_snippets": [],
                "retrieval_results": {},
                "benchmark_lessons": [],
                "few_shot_examples": [],
                "created_at": "2026-01-01T00:00:00+00:00",
            }

        plan = self.runtime.plan_for_stage(
            stage="intake",
            stage_state={},
            payload={"project_slug": "proj", "text": "hello", "topic_type": "general", "lane": "research"},
            run_id="run_x",
            pipeline="research_pipeline",
            spec_stages=list(spec.stages),
            current_context_pack=builder("intake", {}, {}, "run_x", "research_pipeline"),
            context_pack_builder=builder,
            memory_state={"free_vram_gb": 2.0},
        )
        self.assertTrue(plan["level1_prefetch"])
        self.assertEqual(plan["level1_prefetch"][0]["stage"], "domain_framing")
        self.assertIn("domain_framing", plan["prefetched_context_packs"])

    def test_pipeline_engine_uses_prefetched_context_cache(self) -> None:
        spec = pipeline_spec_for_name("research_pipeline")
        assert spec is not None

        state_store = StateStore(self.repo_root)
        engine = PipelineEngine(state_store=state_store)

        call_counts: dict[str, int] = {}

        def builder(stage: str, _stage_state: dict, _payload: dict, run_id: str, pipeline: str) -> dict:
            call_counts[stage] = call_counts.get(stage, 0) + 1
            return {
                "context_pack_id": f"ctx_{stage}_{call_counts[stage]}",
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
                "included_memory": [],
                "excluded_memory_reasoning": [],
                "memory_snippets": [],
                "retrieval_results": {},
                "benchmark_lessons": [],
                "few_shot_examples": [],
                "created_at": "2026-01-01T00:00:00+00:00",
            }

        def on_deck_planner(
            stage: str,
            stage_state: dict,
            payload: dict,
            run_id: str,
            pipeline: str,
            planner_context: dict,
        ) -> dict:
            stages = planner_context.get("spec_stages", []) if isinstance(planner_context.get("spec_stages", []), list) else []
            if stage not in stages:
                return {}
            idx = stages.index(stage)
            if idx + 1 >= len(stages):
                return {"level1_prefetch": [], "prefetched_context_packs": {}}
            next_stage = stages[idx + 1]
            prefetched = builder(next_stage, stage_state, payload, run_id, pipeline)
            return {
                "level1_prefetch": [{"stage": next_stage}],
                "prefetched_context_packs": {next_stage: prefetched},
            }

        def runner(stage: str, _stage_state: dict, payload: dict) -> dict:
            self.assertIn("context_pack", payload)
            self.assertIn("on_deck_plan", payload)
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
            context_pack_builder=builder,
            on_deck_planner=on_deck_planner,
        )

        self.assertTrue(result["ok"])
        self.assertEqual(call_counts.get("domain_framing", 0), 1)
        self.assertEqual(call_counts.get("source_discovery", 0), 1)
        self.assertEqual(call_counts.get("evidence_analysis", 0), 1)
        self.assertEqual(len(result.get("on_deck_plans", {})), len(spec.stages))

    def test_bench_manager_budget_hint_reacts_to_cold_pressure(self) -> None:
        _ = self.bench.build_snapshot(
            run_id="run_pressure_1",
            pipeline="research_pipeline",
            stage="synthesis",
            current_manifest={"specialist_role": "synthesizer"},
            on_deck_entries=[],
            warm_entries=[],
            cold_entries=[{"stage": "a"}, {"stage": "b"}, {"stage": "c"}, {"stage": "d"}],
        )
        hinted = self.bench.recommended_stage_budget(default_budget=1800)
        self.assertLess(hinted, 1800)


if __name__ == "__main__":
    unittest.main()
