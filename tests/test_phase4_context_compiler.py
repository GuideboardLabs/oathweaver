from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from tests.common import ensure_runtime  # noqa: F401
from cag.decision_ledger import DecisionLedger
from cag.memory_store import CAGMemoryStore
from core.context_compiler import ContextCompiler
from core.context_pack import ContextPackStore
from core.pipeline_engine import PipelineEngine, pipeline_spec_for_name
from core.state_store import StateStore


class Phase4ContextCompilerTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory(prefix="phase4_context_compiler_")
        self.repo_root = Path(self.tmp.name)
        ensure_runtime(self.repo_root)
        self.state_store = StateStore(self.repo_root)
        self.pipeline_engine = PipelineEngine(state_store=self.state_store)
        self.context_pack_store = ContextPackStore(self.repo_root)
        self.compiler = ContextCompiler(context_pack_store=self.context_pack_store)
        self.memory_store = CAGMemoryStore(self.repo_root)
        self.ledger = DecisionLedger(self.repo_root)

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def test_compiler_creates_stage_specific_context_pack_and_persists_artifact(self) -> None:
        accepted_memory = self.memory_store.add_row(
            {
                "text": "We must keep inference local-only and avoid cloud APIs.",
                "scope": "level=project|domain=cs|topic=runtime|thread=t1|project=proj|run=r1",
                "scope_level": "project",
                "domain": "cs",
                "topic": "runtime",
                "thread": "t1",
                "project": "proj",
                "run": "r1",
                "type": "constraint",
                "status": "accepted",
                "evidence": [{"kind": "citation", "value": "src-1"}],
                "confidence": 0.9,
                "human_status": "accepted",
                "tags": ["runtime", "local"],
                "promoted_terms": ["local-only"],
                "validation": {"task_metadata": True, "has_citation": True},
            }
        )
        decision = self.ledger.add_entry(memory_row=accepted_memory, rationale="accepted", status="accepted")
        assert decision is not None

        kernel = {
            "knowledge_spine": {
                "domain": "computer_science",
                "topic": "runtime",
                "thread": "t1",
            }
        }
        pack_planner = self.compiler.compile(
            run_id="run_abc",
            pipeline="code_fix_pipeline",
            stage="planner",
            input_payload={
                "project_slug": "proj",
                "text": "Refactor runtime scheduler.",
                "topic_type": "programming",
                "lane": "make_tool",
            },
            stage_state={},
            project_kernel=kernel,
            memory_rows=self.memory_store.list_rows(project="proj", include_superseded=True, include_expired=True, limit=50),
            decision_rows=self.ledger.list_entries(project="proj"),
            benchmark_lessons=["Low continuity recall means retrieval profile is weak."],
            output_contract="planner_contract_v1",
            hardware_token_budget=700,
        )
        pack_synthesis = self.compiler.compile(
            run_id="run_abc",
            pipeline="research_pipeline",
            stage="synthesis",
            input_payload={
                "project_slug": "proj",
                "text": "Summarize runtime constraints with evidence.",
                "topic_type": "programming",
                "lane": "research",
            },
            stage_state={"source_discovery": {"source_count": 3, "web_note": "captured official docs"}},
            project_kernel=kernel,
            memory_rows=self.memory_store.list_rows(project="proj", include_superseded=True, include_expired=True, limit=50),
            decision_rows=self.ledger.list_entries(project="proj"),
            benchmark_lessons=[],
            output_contract="synthesis_contract_v1",
            hardware_token_budget=700,
        )

        self.assertNotEqual(pack_planner["specialist_role"], pack_synthesis["specialist_role"])
        self.assertTrue(pack_planner["included_memory"])
        self.assertIn(accepted_memory["memory_id"], pack_planner["included_memory"])

        run_dir = self.repo_root / "Runtime" / "context_packs" / "run_abc"
        self.assertTrue(run_dir.exists())
        saved = list(run_dir.glob("*.json"))
        self.assertGreaterEqual(len(saved), 2)

    def test_pipeline_engine_injects_context_pack_per_stage(self) -> None:
        spec = pipeline_spec_for_name("research_pipeline")
        assert spec is not None
        seen_stages: list[str] = []

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
                "included_memory": [],
                "excluded_memory_reasoning": [],
                "memory_snippets": [],
                "retrieval_results": {},
                "benchmark_lessons": [],
                "few_shot_examples": [],
                "created_at": "2026-01-01T00:00:00+00:00",
            }

        def runner(stage: str, _stage_state: dict, payload: dict) -> dict:
            self.assertIn("context_pack", payload)
            self.assertEqual(payload["context_pack"]["stage"], stage)
            seen_stages.append(stage)
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

        result = self.pipeline_engine.execute(
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
        self.assertEqual(len(seen_stages), len(spec.stages))
        self.assertEqual(len(result.get("context_packs", {})), len(spec.stages))


if __name__ == "__main__":
    unittest.main()
