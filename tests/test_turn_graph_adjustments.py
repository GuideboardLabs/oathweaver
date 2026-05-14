from __future__ import annotations

import unittest

from tests.common import ROOT  # noqa: F401
from orchestrator.pipelines.turn_graph import _derive_context_gate, _normalize_precomputed_route, _select_lane


class _StubOrchestrator:
    def __init__(self, analysis: dict[str, object]) -> None:
        self.analysis = analysis
        self.turn_planner = object()

    def _context_bundle_for_query(self, text: str, *, household_chars: int = 900):  # noqa: ARG002
        return dict(self.analysis), "", "use context quietly"


class TurnGraphAdjustmentTests(unittest.TestCase):
    def test_normalize_precomputed_route_filters_values(self) -> None:
        route = _normalize_precomputed_route(
            {
                "lane_hint": " Conversation ",
                "domain": " General_Research ",
                "make_type": " Web_App ",
                "ignored": "value",
            }
        )
        self.assertEqual(
            route,
            {
                "lane_hint": "conversation",
                "domain": "general_research",
                "make_type": "web_app",
            },
        )

    def test_context_gate_marks_personal_queries_not_foraging_eligible(self) -> None:
        orchestrator = _StubOrchestrator({"family_query": True, "explicit_memory_query": False})
        gate = _derive_context_gate(orchestrator, text="How is my family doing?", lane="research")
        self.assertTrue(gate["context_gate"]["personal_context"])
        self.assertFalse(gate["foraging_plan"]["eligible"])
        self.assertEqual(gate["context_gate"]["guidance"], "use context quietly")

    def test_select_lane_uses_precomputed_route_without_planner(self) -> None:
        class _PlannerOrchestrator:
            def __init__(self) -> None:
                class _Planner:
                    @staticmethod
                    def plan(*_args, **_kwargs):
                        raise AssertionError("planner should not be called when route is precomputed")

                self.turn_planner = _Planner()

        lane = _select_lane(
            _PlannerOrchestrator(),
            "hello",
            history=[],
            precomputed_route={"lane_hint": "conversation"},
        )
        self.assertEqual(lane, "conversation")


if __name__ == "__main__":
    unittest.main()
