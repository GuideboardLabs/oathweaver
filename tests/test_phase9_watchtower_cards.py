from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from tests.common import ensure_runtime  # noqa: F401
from cag.memory_store import CAGMemoryStore
from core.project_kernel import ProjectKernelStore
from shared_tools.watchtower import WatchtowerEngine


class Phase9WatchtowerCardsTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory(prefix="phase9_watchtower_")
        self.repo_root = Path(self.tmp.name)
        ensure_runtime(self.repo_root)
        self.watchtower = WatchtowerEngine(self.repo_root)
        self.kernel_store = ProjectKernelStore(self.repo_root)
        self.cag_store = CAGMemoryStore(self.repo_root)

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def test_scan_emits_scoped_gap_cards_without_cag_mutation(self) -> None:
        self.kernel_store.update_for_turn(
            project_id="general",
            lane="research",
            topic_type="programming",
            query_text="Design scoped CAG memory selector",
            query_mode="implementation_focused",
        )
        kernel = self.kernel_store.snapshot("general")
        auditor_report = {
            "run_id": "run_phase9_1",
            "typed_findings": [
                {"type": "missing topic knowledge", "severity": "high", "evidence": "low_continuity"},
                {"type": "wrong memory scope", "severity": "high", "evidence": "selector_breadth"},
                {"type": "wrong specialist mix", "severity": "medium", "evidence": "roles_missing"},
            ],
            "benchmark_snapshot": {
                "signals": {
                    "continuity_recall": 29.0,
                    "memory_usage_rate": 84.0,
                    "score": 39.0,
                    "high_memory_low_continuity": True,
                    "high_memory_low_score": True,
                }
            },
        }

        before_count = len(self.cag_store.list_rows(project="general", include_expired=True, include_superseded=True, limit=500))
        scan = self.watchtower.scan_project_gaps(project="general", project_kernel=kernel, auditor_report=auditor_report)
        after_count = len(self.cag_store.list_rows(project="general", include_expired=True, include_superseded=True, limit=500))

        self.assertEqual(before_count, after_count)
        self.assertGreaterEqual(int(scan.get("queued_count", 0)), 3)

        cards = self.watchtower.list_cards(limit=50)
        card_types = {str(row.get("card_type", "")) for row in cards}
        self.assertIn("knowledge_gap_card", card_types)
        self.assertIn("benchmark_gap_card", card_types)
        self.assertIn("capability_gap_card", card_types)
        for row in cards:
            self.assertEqual(str(row.get("status", "")), "queued")
            self.assertIn(str(row.get("scope_level", "")), {"domain", "topic", "thread", "project"})

    def test_research_card_queue_and_status_transitions(self) -> None:
        queued = self.watchtower.scout.queue_research_card_from_briefing(
            briefing={
                "id": "brief_01",
                "watch_id": "watch_01",
                "domain": "programming",
                "topic": "llm runtime",
                "headline": "Local runtime scheduler update",
                "summary": "Two architecture paths emerged for prefetch scheduling.",
            }
        )
        self.assertEqual(str(queued.get("card_type", "")), "research_card")
        self.assertEqual(str(queued.get("status", "")), "queued")

        accepted = self.watchtower.set_card_status(
            str(queued.get("id", "")),
            status="accepted",
            note="Run this after next auditor cycle.",
        )
        self.assertIsNotNone(accepted)
        self.assertEqual(str((accepted or {}).get("status", "")), "accepted")


if __name__ == "__main__":
    unittest.main()
