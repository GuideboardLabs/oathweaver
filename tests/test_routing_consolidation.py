from __future__ import annotations

import unittest

from tests.common import ROOT  # noqa: F401
from orchestrator.intent_router import IntentRouter
from orchestrator.services.policy import RoutingPolicy, classify_query_mode, estimate_query_complexity
from shared_tools.query_router import recommend_lane_override, should_run_full_foraging


class RoutingConsolidationTests(unittest.TestCase):
    def test_legacy_wrappers_point_to_policy_surface(self) -> None:
        router = IntentRouter()
        self.assertEqual(router.route('Build me a web app', project_slug='general'), 'ui')
        self.assertEqual(classify_query_mode('Refactor this python function'), 'workspace_code')
        self.assertEqual(estimate_query_complexity('What time is the fight tonight?'), 'simple')
        self.assertEqual(recommend_lane_override('personal_home', 'research'), 'personal')
        self.assertFalse(should_run_full_foraging('simple_factual', 'simple'))

    def test_policy_decision_is_single_source_of_truth(self) -> None:
        policy = RoutingPolicy(ROOT)
        decision = policy.decide(
            'Compare the long-term tradeoffs of SQLite vs PostgreSQL for a local-first AI app',
            project_slug='oathweaver',
            topic_type='technical',
        )
        self.assertEqual(decision.lane, 'research')
        self.assertEqual(decision.query_mode, 'deep_research')
        self.assertEqual(decision.lane_override, 'research')
        self.assertTrue(decision.meta['words'] >= 5)


if __name__ == '__main__':
    unittest.main()
