from __future__ import annotations

import unittest

from tests.common import ROOT  # noqa: F401
from orchestrator.main import OathweaverOrchestrator


class _FakeSelector:
    def __init__(self) -> None:
        self.calls: list[dict] = []

    def retrieve_scoped(self, *, task, rows, k):
        self.calls.append({"task": task, "rows": list(rows), "k": k})
        return list(rows)[:k]


class ContextPackCagRetrievalTests(unittest.TestCase):
    def test_context_pack_uses_scoped_selector_with_project_plus_domain_rows(self) -> None:
        selector = _FakeSelector()
        payload = {
            "text": "Build a plant tracker MVP",
            "domain": "computer_science_programming",
            "target": "web_app",
        }
        project_rows = [{"memory_id": "m_project"}]
        domain_rows = [{"memory_id": "m_seed"}]
        out = OathweaverOrchestrator._select_context_memory_rows(
            selector, payload=payload, project_rows=project_rows, domain_rows=domain_rows
        )
        self.assertEqual(len(selector.calls), 1)
        call = selector.calls[0]
        self.assertEqual(call["k"], 40)
        self.assertEqual(len(call["rows"]), 2)
        self.assertIn("computer_science_programming", call["task"]["tags"])
        self.assertIn("web_app", call["task"]["tags"])
        self.assertEqual(out[0]["memory_id"], "m_project")


if __name__ == "__main__":
    unittest.main()

