from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from tests.common import ROOT  # noqa: F401
from orchestrator.main import OathweaverOrchestrator
from orchestrator.services.self_query_gate import SelfQueryGate
from orchestrator.services.self_state import SelfStateService


class _EmbedStub:
    def embed(self, model: str, text: str, *, timeout: int = 20) -> list[float]:  # noqa: ARG002
        low = str(text or "").lower()
        buckets = [
            ("model", ("model", "llm")),
            ("routing", ("fallback", "routing", "pick")),
            ("backend", ("backend", "ollama", "llama.cpp")),
            ("loaded", ("loaded", "vram", "kv")),
            ("hardware", ("gpu", "cuda", "rocm", "hardware")),
            ("capability", ("capabilities", "context", "tools")),
            ("general", ("config", "setup", "state")),
        ]
        vec = [0.0] * len(buckets)
        for idx, (_, words) in enumerate(buckets):
            for word in words:
                if word in low:
                    vec[idx] += 1.0
        norm = sum(v * v for v in vec) ** 0.5
        return [v / norm for v in vec] if norm else vec


class _RouterStub:
    def explain_route(self, task_class: str = "chat_layer") -> dict[str, object]:
        _ = task_class
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
        return {"backends": [{"name": "ollama", "reachable": True, "models": ["dolphin3:8b"]}]}

    def memory_state(self) -> dict[str, object]:
        return {"loaded_models": ["dolphin3:8b"], "vram_used_gb": 6.4, "vram_capacity_gb": 12.0, "kv_pressure": 0.18}

    def validate_config(self, profile: dict[str, object] | None = None) -> dict[str, object]:
        _ = profile
        return {"warnings": [], "errors": []}


class _CapabilityRegistryStub:
    def list_recent_claims(self, limit: int = 5):  # noqa: ANN001
        _ = limit
        return []


class _CAGStoreStub:
    def count_rows(self, project: str = "") -> int:
        _ = project
        return 3


def _profile() -> dict[str, object]:
    return {
        "name": "8gb_vram_16gb_ram",
        "display_name": "Default: 8GB VRAM / 16GB RAM",
        "hardware": {"gpu_backend": "generic", "gpu_vram_gb": 8},
        "scheduler": {"max_context_tokens": 4096},
        "model_policy": {"allow_premium": False},
    }


class SelfStateIntegrationTests(unittest.TestCase):
    def test_model_and_hardware_queries_surface_literal_values(self) -> None:
        tmp = tempfile.TemporaryDirectory(prefix="self_state_integration_")
        repo_root = Path(tmp.name)
        try:
            orch = OathweaverOrchestrator.__new__(OathweaverOrchestrator)
            orch.self_query_gate = SelfQueryGate(_EmbedStub(), threshold=0.75, repo_root=repo_root)
            orch.self_state_service = SelfStateService(
                router=_RouterStub(),
                capability_registry=_CapabilityRegistryStub(),
                cag_store=_CAGStoreStub(),
                hardware_profile_provider=_profile,
                project_slug_provider=lambda: "general",
            )

            model_block, _ = orch._build_self_state_block("what model are you running", role_scope="owner")
            hw_block, _ = orch._build_self_state_block("what gpu are you on", role_scope="owner")

            self.assertIn("chat_layer.model: dolphin3:8b", model_block)
            self.assertIn("hardware_profile.gpu_backend: generic", hw_block)
        finally:
            tmp.cleanup()


if __name__ == "__main__":
    unittest.main()
