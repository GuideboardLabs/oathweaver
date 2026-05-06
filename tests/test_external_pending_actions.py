from __future__ import annotations

import shutil
import unittest
from pathlib import Path

from tests.common import ROOT, ensure_runtime
from orchestrator.main import OathweaverOrchestrator
from shared_tools.external_requests import ExternalRequestStore, ExternalToolsSettings


class ExternalPendingActionsTests(unittest.TestCase):
    def setUp(self) -> None:
        self.runtime_tmp = Path(ROOT) / "Runtime" / "test_external_pending_tmp"
        if self.runtime_tmp.exists():
            shutil.rmtree(self.runtime_tmp, ignore_errors=True)
        self.repo_root = self.runtime_tmp / "repo"
        self.repo_root.mkdir(parents=True, exist_ok=True)
        ensure_runtime(self.repo_root)
        self.store = ExternalRequestStore(self.repo_root)
        self.settings = ExternalToolsSettings(self.repo_root)
        self.orch = OathweaverOrchestrator(self.repo_root)

    def tearDown(self) -> None:
        shutil.rmtree(self.runtime_tmp, ignore_errors=True)

    def test_mode_off_hides_external_requests_from_pending_actions(self) -> None:
        req = self.store.create(
            {
                "provider": "openclaw",
                "intent": "send_email",
                "project": "general",
                "lane": "project",
                "summary": "Email task request",
            }
        )
        self.assertEqual(self.settings.get_mode(), "off")
        actions = self.orch.pending_actions_data(limit=200)
        self.assertFalse(any(str(x.get("id", "")) == str(req.get("id", "")) for x in actions))
        still_open = self.store.get(str(req.get("id", "")))
        self.assertEqual(still_open["status"], "queued")

    def test_mode_ask_surfaces_external_requests_with_extended_fields(self) -> None:
        self.settings.set_mode("ask")
        req = self.store.create(
            {
                "provider": "openclaw",
                "intent": "task_suggestion",
                "project": "general",
                "lane": "project",
                "summary": "Suggest school pickup reminders",
                "result_json": {"suggestions": [{"type": "task", "title": "Pickup"}]},
            }
        )
        actions = self.orch.pending_actions_data(limit=200)
        row = next((x for x in actions if str(x.get("id", "")) == str(req.get("id", ""))), None)
        self.assertIsNotNone(row)
        self.assertEqual(row["type"], "external_request")
        self.assertEqual(row["provider"], "openclaw")
        self.assertEqual(row["intent"], "task_suggestion")
        self.assertEqual(row["status"], "queued")
        self.assertEqual(int(row.get("suggestions_count", 0)), 1)

    def test_answer_archives_external_request_without_dispatch(self) -> None:
        self.settings.set_mode("ask")
        req = self.store.create(
            {
                "provider": "openclaw",
                "intent": "event_suggestion",
                "project": "general",
                "lane": "project",
                "summary": "Suggest family event",
            }
        )
        msg = self.orch.answer_pending_action(str(req.get("id", "")), "not now")
        self.assertTrue(msg.lower().startswith("pending action ignored"))
        updated = self.store.get(str(req.get("id", "")))
        self.assertEqual(updated["status"], "ignored")
        self.assertTrue(bool(updated["result_json"].get("dispatch_blocked", False)))

    def test_existing_pending_types_still_serialize(self) -> None:
        self.settings.set_mode("ask")
        self.store.create(
            {
                "provider": "openclaw",
                "intent": "send_email",
                "project": "general",
                "lane": "project",
                "summary": "External example",
            }
        )
        self.orch.web_engine.create_pending(
            project="general",
            lane="research",
            query="latest weather in boston",
            reason="recency check",
            topic_type="general",
        )
        self.orch.topic_memory.create_pending_review(
            "family",
            "fact_abc",
            "Kids soccer practice is on Tuesday.",
            confidence=0.7,
            source="memory",
            source_file="Runtime/state/oathweaver.db",
            project="general",
        )
        actions = self.orch.pending_actions_data(limit=200)
        kinds = {str(x.get("type", "")) for x in actions}
        self.assertIn("external_request", kinds)
        self.assertIn("web_research", kinds)
        self.assertIn("topic_review", kinds)


if __name__ == "__main__":
    unittest.main()
