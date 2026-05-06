from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from tests.common import ensure_runtime  # noqa: F401

from core.model_runtime import LlamaCppModelRuntime, OllamaModelRuntime, build_model_runtime
from core.pipeline_engine import PipelineEngine, pipeline_spec_for_name
from core.state_store import StateStore


class _StubRuntime:
    def __init__(self) -> None:
        self.calls = 0

    def get_memory_state(self) -> dict:
        self.calls += 1
        return {
            "backend": "stub",
            "free_vram_gb": 1.75,
            "kv_pressure": 0.42,
            "loaded_model": "qwen3:8b",
        }


class _OllamaRuntimeWithMockedPS(OllamaModelRuntime):
    def _read_ps_json(self) -> dict:
        return {
            "models": [
                {
                    "name": "qwen3:8b",
                    "adapter": "memory_critic_lora",
                    "size_vram": "3.5 GB",
                    "gpu_total": "8 GB",
                    "kv_cache_usage": 0.35,
                }
            ]
        }


class _LlamaClientStub:
    def chat(self, *args, **kwargs):  # pragma: no cover
        return "ok"

    def list_local_models(self) -> list[str]:
        return ["qwen3-8b-q4_k_m.gguf"]


class Phase11ModelRuntimeAbstractionTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory(prefix="phase11_model_runtime_")
        self.repo_root = Path(self.tmp.name)
        ensure_runtime(self.repo_root)

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def test_pipeline_engine_passes_model_memory_state_to_on_deck(self) -> None:
        spec = pipeline_spec_for_name("research_pipeline")
        assert spec is not None

        state_store = StateStore(self.repo_root)
        engine = PipelineEngine(state_store=state_store)
        runtime = _StubRuntime()
        seen_states: list[dict] = []

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

        def on_deck_planner(stage: str, _stage_state: dict, payload: dict, _run_id: str, _pipeline: str, _ctx: dict) -> dict:
            row = payload.get("model_memory_state", {}) if isinstance(payload.get("model_memory_state", {}), dict) else {}
            seen_states.append(dict(row))
            return {"level1_prefetch": [], "level2_prefetch": [], "prefetched_context_packs": {}}

        def runner(stage: str, _stage_state: dict, payload: dict) -> dict:
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
            model_runtime=runtime,
        )
        self.assertTrue(result.get("ok"))
        self.assertEqual(runtime.calls, len(spec.stages))
        self.assertTrue(seen_states)
        self.assertAlmostEqual(float(seen_states[0].get("free_vram_gb", 0.0) or 0.0), 1.75, places=2)

    def test_ollama_runtime_get_memory_state_shape(self) -> None:
        runtime = _OllamaRuntimeWithMockedPS(self.repo_root)
        state = runtime.get_memory_state()
        self.assertEqual(str(state.get("backend", "")), "ollama")
        self.assertEqual(str(state.get("loaded_model", "")), "qwen3:8b")
        self.assertEqual(str(state.get("loaded_adapter", "")), "memory_critic_lora")
        self.assertGreater(float(state.get("free_vram_gb", 0.0) or 0.0), 4.0)
        self.assertAlmostEqual(float(state.get("kv_pressure", 0.0) or 0.0), 0.35, places=2)

    def test_runtime_factory_and_llamacpp_memory_state(self) -> None:
        runtime = build_model_runtime(self.repo_root, backend="llamacpp")
        self.assertIsInstance(runtime, LlamaCppModelRuntime)

        llm = LlamaCppModelRuntime(self.repo_root, client=_LlamaClientStub())
        state = llm.get_memory_state()
        self.assertEqual(str(state.get("backend", "")), "llama.cpp")
        self.assertEqual(str(state.get("loaded_model", "")), "qwen3-8b-q4_k_m.gguf")


if __name__ == "__main__":
    unittest.main()
