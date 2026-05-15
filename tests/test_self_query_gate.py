from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from tests.common import ROOT  # noqa: F401
from orchestrator.services.self_query_gate import SelfQueryGate


class _EmbedStub:
    def __init__(self) -> None:
        self.calls = 0

    def embed(self, model: str, text: str, *, timeout: int = 20) -> list[float]:  # noqa: ARG002
        self.calls += 1
        low = str(text or "").lower()
        dims = [
            ("model", ("model", "llm")),
            ("routing", ("fallback", "routing", "pick")),
            ("backend", ("backend", "ollama", "llama.cpp")),
            ("loaded", ("loaded", "vram", "kv")),
            ("hardware", ("gpu", "cuda", "rocm", "hardware")),
            ("capability", ("capabilities", "context", "tools")),
            ("general", ("config", "setup", "state")),
        ]
        vec: list[float] = []
        for _, words in dims:
            score = 0.0
            for word in words:
                if word in low:
                    score += 1.0
            vec.append(score)
        norm = sum(v * v for v in vec) ** 0.5
        if norm > 0:
            vec = [v / norm for v in vec]
        return vec


class SelfQueryGateTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory(prefix="self_query_gate_")
        self.repo_root = Path(self.tmp.name)

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def test_classifies_model_and_hardware_queries(self) -> None:
        gate = SelfQueryGate(_EmbedStub(), threshold=0.75, repo_root=self.repo_root)

        model_decision = gate.classify("what model are you running")
        hardware_decision = gate.classify("what gpu are you on")

        self.assertTrue(model_decision.is_self_query)
        self.assertEqual(model_decision.match_kind, "model")
        self.assertTrue(hardware_decision.is_self_query)
        self.assertEqual(hardware_decision.match_kind, "hardware")

    def test_rejects_non_self_query(self) -> None:
        gate = SelfQueryGate(_EmbedStub(), threshold=0.75, repo_root=self.repo_root)

        decision = gate.classify("what car should i buy")

        self.assertFalse(decision.is_self_query)
        self.assertEqual(decision.match_kind, "")

    def test_rejects_adversarial_near_misses(self) -> None:
        gate = SelfQueryGate(_EmbedStub(), threshold=0.75, repo_root=self.repo_root)
        near_misses = [
            "what model car should i buy",
            "tell me about ollama in general",
        ]
        for text in near_misses:
            with self.subTest(text=text):
                decision = gate.classify(text)
                self.assertFalse(decision.is_self_query)
                self.assertEqual(decision.match_kind, "")

    def test_threshold_edge_cases(self) -> None:
        gate = SelfQueryGate(_EmbedStub(), threshold=0.99, repo_root=self.repo_root)
        decision = gate.classify("hello there")
        self.assertFalse(decision.is_self_query)

        gate2 = SelfQueryGate(_EmbedStub(), threshold=0.25, repo_root=self.repo_root)
        decision2 = gate2.classify("what model are you running")
        self.assertTrue(decision2.is_self_query)

    def test_cached_exemplar_load_avoids_reembedding(self) -> None:
        embed1 = _EmbedStub()
        gate1 = SelfQueryGate(embed1, threshold=0.75, repo_root=self.repo_root)
        _ = gate1.classify("what model are you running")
        first_calls = embed1.calls

        embed2 = _EmbedStub()
        gate2 = SelfQueryGate(embed2, threshold=0.75, repo_root=self.repo_root)
        _ = gate2.classify("what model are you running")

        self.assertGreater(first_calls, 10)
        self.assertEqual(embed2.calls, 1)


if __name__ == "__main__":
    unittest.main()
