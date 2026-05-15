from __future__ import annotations

import unittest

from tests.common import ROOT  # noqa: F401
from orchestrator.services.policy import _resolve_domain as policy_resolve
from orchestrator.pipelines.turn_graph import _resolve_domain as graph_resolve


class ResolveDomainDedupTests(unittest.TestCase):
    def test_turn_graph_uses_policy_resolver(self) -> None:
        self.assertIs(policy_resolve, graph_resolve)

    def test_code_make_types_force_programming_domain(self) -> None:
        self.assertEqual(policy_resolve("web_app", "history"), "computer_science_programming")
        self.assertEqual(policy_resolve("desktop_app", "science"), "computer_science_programming")

    def test_non_code_make_type_keeps_inferred_domain_with_general_fallback(self) -> None:
        self.assertEqual(policy_resolve("essay_long", "history"), "history")
        self.assertEqual(policy_resolve("essay_long", ""), "general_research")

    def test_unknown_make_type_falls_back_to_inferred_domain(self) -> None:
        self.assertEqual(policy_resolve("unknown_type", "biology"), "biology")

    def test_code_make_type_with_blank_inferred_domain_still_forces_programming(self) -> None:
        self.assertEqual(policy_resolve("web_app", ""), "computer_science_programming")


if __name__ == "__main__":
    unittest.main()
