from __future__ import annotations

import unittest
from pathlib import Path

from taxonomy.domains import domain_for_topic_type, normalize_domain
from taxonomy.make_types import infer_make_type, normalize_make_type
from taxonomy.research_focus import infer_research_focus, normalize_research_focus
from orchestrator.services.policy import RoutingPolicy


class _FixedIntentRouter:
    def __init__(self, lane: str) -> None:
        self._lane = lane

    def route(self, *_args, **_kwargs) -> str:
        return self._lane


class Phase1HierarchyTaxonomyTests(unittest.TestCase):
    def test_domain_normalization_and_topic_type_mapping(self) -> None:
        self.assertEqual(normalize_domain("programming"), "computer_science_programming")
        self.assertEqual(domain_for_topic_type("animal_care"), "science")
        self.assertEqual(domain_for_topic_type("technical"), "computer_science_programming")

    def test_make_type_normalization_and_inference(self) -> None:
        self.assertEqual(normalize_make_type("webapp"), "web_app")
        self.assertEqual(infer_make_type(text="Need a benchmark suite for runtime tuning", lane="research"), "benchmark_suite")
        self.assertEqual(infer_make_type(text="Please scaffold this", lane="make_tool"), "developer_tool")

    def test_research_focus_normalization_and_inference(self) -> None:
        self.assertEqual(normalize_research_focus("evidence-focused"), "evidence_focused")
        self.assertEqual(
            infer_research_focus(
                text="Verify each claim with source evidence",
                query_mode="general_research",
                pipeline="research_pipeline",
                make_type="research_brief",
            ),
            "evidence_focused",
        )

    def test_routing_policy_separates_domain_from_make_intent(self) -> None:
        policy = RoutingPolicy(Path("/tmp"), intent_router=_FixedIntentRouter("make_tool"))
        decision = policy.decide(
            "Patch this Python file and refactor the function.",
            project_slug="general",
            topic_type="technical",
            current_lane="research",
        )
        self.assertEqual(decision.domain, "computer_science_programming")
        self.assertEqual(decision.make_intent, "workspace_code")
        self.assertEqual(decision.pipeline, "build_pipeline")
        self.assertEqual(decision.research_focus, "implementation_focused")


if __name__ == "__main__":
    unittest.main()
