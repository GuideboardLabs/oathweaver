from __future__ import annotations

import unittest

from tests.common import ROOT  # noqa: F401
from orchestrator.services.self_state import SelfStateService


class _RouterStub:
    def __init__(self) -> None:
        self.health_calls = 0
        self.memory_calls = 0
        self.explain_calls = 0
        self.validate_calls = 0

    def explain_route(self, task_class: str = "chat_layer") -> dict[str, object]:
        _ = task_class
        self.explain_calls += 1
        return {
            "selected_model": "dolphin3:8b",
            "backend": "ollama",
            "fallback_chain": ["dolphin3:8b", "qwen3:8b"],
        }

    def context_window(self, model: str) -> int:
        _ = model
        return 8192

    def capabilities(self, model: str) -> dict[str, object]:
        _ = model
        return {"size_b": 8.0, "weight_class": "normal", "reasoning": False}

    def health_report(self) -> dict[str, object]:
        self.health_calls += 1
        return {"backends": [{"name": "ollama", "reachable": True, "models": ["dolphin3:8b"]}]}

    def memory_state(self) -> dict[str, object]:
        self.memory_calls += 1
        return {
            "loaded_models": ["dolphin3:8b"],
            "vram_used_gb": 6.4,
            "vram_capacity_gb": 12.0,
            "kv_pressure": 0.18,
        }

    def validate_config(self, profile: dict[str, object] | None = None) -> dict[str, object]:
        _ = profile
        self.validate_calls += 1
        return {"warnings": ["ctx warning"], "errors": []}


class _CapabilityRegistryStub:
    def list_recent_claims(self, limit: int = 5):  # noqa: ANN001
        _ = limit
        return [{"created_at": "2026-05-13T00:00:00+00:00", "claim": "claim-1"}]


class _CAGStoreStub:
    def count_rows(self, project: str = "") -> int:
        _ = project
        return 1247


def _profile() -> dict[str, object]:
    return {
        "name": "8gb_vram_16gb_ram",
        "display_name": "Default: 8GB VRAM / 16GB RAM",
        "hardware": {"gpu_backend": "generic", "gpu_vram_gb": 8},
        "scheduler": {"max_context_tokens": 4096},
        "model_policy": {"allow_premium": False},
    }


class SelfStateServiceTests(unittest.TestCase):
    def setUp(self) -> None:
        self.router = _RouterStub()
        self.service = SelfStateService(
            router=self.router,
            capability_registry=_CapabilityRegistryStub(),
            cag_store=_CAGStoreStub(),
            hardware_profile_provider=_profile,
            project_slug_provider=lambda: "oathweaver_v1",
        )

    def test_block_formatting_for_model_kind(self) -> None:
        state = self.service.compute("model", role="owner")
        block = state.to_prompt_block("model")
        self.assertIn("chat_layer.model: dolphin3:8b", block)
        self.assertIn("loaded_models: ['dolphin3:8b']", block)
        self.assertNotIn("project:", block)

    def test_health_cache_reused_within_ttl(self) -> None:
        _ = self.service.compute("general", role="owner")
        _ = self.service.compute("general", role="owner")
        self.assertEqual(self.router.health_calls, 1)
        self.assertEqual(self.router.memory_calls, 1)

    def test_hardware_cache_reused_within_ttl(self) -> None:
        _ = self.service.compute("hardware", role="owner")
        _ = self.service.compute("hardware", role="owner")
        self.assertEqual(self.router.validate_calls, 1)

    def test_guest_redaction_hides_sensitive_fields(self) -> None:
        state = self.service.compute("general", role="guest")
        block = state.to_prompt_block("general")
        self.assertEqual(state.chat_layer_model, "dolphin3:8b")
        self.assertEqual(state.hardware_profile_display_name, "Default: 8GB VRAM / 16GB RAM")
        self.assertEqual(state.backends, [])
        self.assertTrue(state.redacted_fields)
        self.assertNotIn("backends.ollama", block)
        self.assertNotIn("project:", block)

    def test_handles_missing_fields_gracefully(self) -> None:
        class _SparseRouter(_RouterStub):
            def health_report(self) -> dict[str, object]:
                self.health_calls += 1
                return {}

            def memory_state(self) -> dict[str, object]:
                self.memory_calls += 1
                return {}

        sparse = SelfStateService(
            router=_SparseRouter(),
            capability_registry=_CapabilityRegistryStub(),
            cag_store=_CAGStoreStub(),
            hardware_profile_provider=lambda: {"name": "x"},
            project_slug_provider=lambda: "general",
        )
        state = sparse.compute("general", role="owner")
        self.assertEqual(state.chat_layer_model, "dolphin3:8b")
        self.assertEqual(state.vram_used_gb, 0.0)


if __name__ == "__main__":
    unittest.main()
