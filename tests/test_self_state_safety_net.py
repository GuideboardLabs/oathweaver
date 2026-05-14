from __future__ import annotations

import unittest

from tests.common import ROOT  # noqa: F401
from orchestrator.main import OathweaverOrchestrator


class SelfStateSafetyNetTests(unittest.TestCase):
    def test_appends_reference_when_ground_truth_missing(self) -> None:
        orch = OathweaverOrchestrator.__new__(OathweaverOrchestrator)
        reply = "I am running a strong model for this task."
        out = orch._apply_self_state_safety_net(
            reply,
            self_query_meta={
                "is_self_query": True,
                "confidence": 0.92,
                "match_kind": "model",
                "top_values": ["dolphin3:8b"],
            },
        )
        self.assertIn("For reference, current configuration:", out)
        self.assertIn("chat_layer.model: dolphin3:8b", out)

    def test_no_append_when_ground_truth_present(self) -> None:
        orch = OathweaverOrchestrator.__new__(OathweaverOrchestrator)
        reply = "Current model is dolphin3:8b."
        out = orch._apply_self_state_safety_net(
            reply,
            self_query_meta={
                "is_self_query": True,
                "confidence": 0.95,
                "match_kind": "model",
                "top_values": ["dolphin3:8b"],
            },
        )
        self.assertEqual(out, reply)


if __name__ == "__main__":
    unittest.main()
