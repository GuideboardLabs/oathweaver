from __future__ import annotations

import unittest

from tests.common import ROOT  # noqa: F401
from orchestrator.services.self_state import SelfStateService


class _RouterStub:
    def explain_route(self, task_class: str = "chat_layer") -> dict[str, object]:
        _ = task_class
        return {"selected_model": "dolphin3:8b", "backend": "ollama", "fallback_chain": ["dolphin3:8b"]}

    def context_window(self, model: str) -> int:
        _ = model
        return 8192

    def capabilities(self, model: str) -> dict[str, object]:
        _ = model
        return {"size_b": 8.0, "weight_class": "normal", "reasoning": False}

    def health_report(self) -> dict[str, object]:
        return {"backends": [{"name": "ollama", "reachable": True, "models": ["dolphin3:8b"]}]}

    def memory_state(self) -> dict[str, object]:
        return {"loaded_models": ["dolphin3:8b"], "vram_used_gb": 4.0, "vram_capacity_gb": 8.0, "kv_pressure": 0.2}

    def validate_config(self, profile: dict[str, object] | None = None) -> dict[str, object]:
        _ = profile
        return {"warnings": ["warn"], "errors": []}


class _CapabilityRegistryStub:
    def list_recent_claims(self, limit: int = 5):  # noqa: ANN001
        _ = limit
        return [{"created_at": "2026-05-01", "claim": "claim-1"}]


class _CAGStoreStub:
    def count_rows(self, project: str = "") -> int:
        _ = project
        return 55


def _profile() -> dict[str, object]:
    return {
        "name": "8gb_vram_16gb_ram",
        "display_name": "Default: 8GB VRAM / 16GB RAM",
        "hardware": {"gpu_backend": "generic", "gpu_vram_gb": 8},
        "scheduler": {"max_context_tokens": 4096},
        "model_policy": {"allow_premium": False},
    }


class SelfStateRedactionTests(unittest.TestCase):
    def setUp(self) -> None:
        self.service = SelfStateService(
            router=_RouterStub(),
            capability_registry=_CapabilityRegistryStub(),
            cag_store=_CAGStoreStub(),
            hardware_profile_provider=_profile,
            project_slug_provider=lambda: "general",
        )

    def test_owner_gets_full_fields(self) -> None:
        state = self.service.compute("general", role="owner")
        self.assertEqual(state.chat_layer_model, "dolphin3:8b")
        self.assertTrue(state.backends)
        self.assertEqual(state.project, "general")
        self.assertEqual(state.redacted_fields, [])

    def test_guest_gets_minimal_fields_and_redaction_list(self) -> None:
        state = self.service.compute("general", role="guest")
        self.assertEqual(state.chat_layer_model, "dolphin3:8b")
        self.assertEqual(state.hardware_profile_display_name, "Default: 8GB VRAM / 16GB RAM")
        self.assertEqual(state.backends, [])
        self.assertEqual(state.project, "")
        self.assertTrue(state.redacted_fields)


if __name__ == "__main__":
    unittest.main()
