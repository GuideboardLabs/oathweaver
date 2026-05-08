from __future__ import annotations

import unittest

from tests.common import ROOT  # noqa: F401
from orchestrator.main import OathweaverOrchestrator


class _Plan:
    def __init__(self, *, make_type: str, domain: str) -> None:
        self.make_type = make_type
        self.domain = domain


class PipelineDomainOverrideTests(unittest.TestCase):
    def test_web_app_make_type_forces_cs_domain(self) -> None:
        plan = _Plan(make_type="web_app", domain="general_research")
        self.assertEqual(
            OathweaverOrchestrator._resolved_pipeline_domain(plan),
            "computer_science_programming",
        )

    def test_non_code_make_type_keeps_inferred_domain(self) -> None:
        plan = _Plan(make_type="essay", domain="history")
        self.assertEqual(OathweaverOrchestrator._resolved_pipeline_domain(plan), "history")


if __name__ == "__main__":
    unittest.main()

