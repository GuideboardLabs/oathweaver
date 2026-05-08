from __future__ import annotations

import unittest

from tests.common import ROOT  # noqa: F401
from orchestrator.services.policy import _resolve_domain as policy_resolve
from orchestrator.pipelines.turn_graph import _resolve_domain as graph_resolve


class ResolveDomainDedupTests(unittest.TestCase):
    def test_turn_graph_uses_policy_resolver(self) -> None:
        self.assertIs(policy_resolve, graph_resolve)


if __name__ == "__main__":
    unittest.main()

