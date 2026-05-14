from __future__ import annotations

import unittest

from tests.common import ROOT  # noqa: F401
from orchestrator.main import OathweaverOrchestrator


class OrchestratorMainTests(unittest.TestCase):
    def test_requires_live_verification_for_recency_sensitive_query(self) -> None:
        orch = OathweaverOrchestrator.__new__(OathweaverOrchestrator)
        orch._is_recency_sensitive = lambda text: "today" in text.lower()  # type: ignore[method-assign]
        self.assertTrue(orch._requires_live_verification("What are today's standings?", "sports_event"))

    def test_requires_live_verification_false_for_stable_query(self) -> None:
        orch = OathweaverOrchestrator.__new__(OathweaverOrchestrator)
        orch._is_recency_sensitive = lambda _text: False  # type: ignore[method-assign]
        self.assertFalse(orch._requires_live_verification("Explain binary search in simple terms.", "general"))

    def test_personal_context_detected_matches_context_flags(self) -> None:
        self.assertTrue(
            OathweaverOrchestrator._personal_context_detected(  # type: ignore[attr-defined]
                {"family_query": True, "explicit_memory_query": False}
            )
        )
        self.assertFalse(
            OathweaverOrchestrator._personal_context_detected(  # type: ignore[attr-defined]
                {"family_query": False, "pet_query": False, "profile_query": False}
            )
        )


if __name__ == "__main__":
    unittest.main()
