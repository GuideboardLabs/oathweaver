from __future__ import annotations

import unittest
from pathlib import Path

from tests.common import ROOT  # noqa: F401  # ensures SourceCode on sys.path
from orchestrator.main import OathweaverOrchestrator


class OrchestratorPersonaTests(unittest.TestCase):
    def setUp(self) -> None:
        self.orch = OathweaverOrchestrator.__new__(OathweaverOrchestrator)
        self.orch.repo_root = Path(ROOT)
        self.orch.manifesto_path = self.orch.repo_root / "Runtime" / "config" / "oathweaver_manifesto.md"
        self.orch._manifesto_cache_mtime = -1.0
        self.orch._manifesto_cache_text = ""

    def test_strip_alias_prefix_for_vocative_address(self) -> None:
        text = self.orch._strip_oathweaver_vocative_prefix("Weaver, add a reminder for tomorrow")
        self.assertEqual(text, "add a reminder for tomorrow")

    def test_strip_oathweaver_prefix_for_vocative_address(self) -> None:
        text = self.orch._strip_oathweaver_vocative_prefix("Oathweaver, add a reminder for tomorrow")
        self.assertEqual(text, "add a reminder for tomorrow")

    def test_does_not_strip_when_alias_is_subject(self) -> None:
        text = self.orch._strip_oathweaver_vocative_prefix("Oathweaver is helping my workflow")
        self.assertEqual(text, "Oathweaver is helping my workflow")

    def test_detects_self_query_with_alias(self) -> None:
        self.assertTrue(self.orch._is_oathweaver_self_query("Oathweaver, what is your tech stack?"))
        self.assertTrue(self.orch._is_oathweaver_self_query("Weaver, who are you?"))
        self.assertFalse(self.orch._is_oathweaver_self_query("Oathweaver set a task for tomorrow"))

    def test_identity_reply_contains_alias_and_origin(self) -> None:
        reply = self.orch._oathweaver_identity_reply().lower()
        self.assertIn("oathweaver", reply)
        self.assertIn("weaver", reply)
        self.assertIn("overseer", reply)
        self.assertIn("seth canfield", reply)
        self.assertIn("elma", reply)

    def test_persona_block_includes_manifesto_principles(self) -> None:
        persona = self.orch._oathweaver_persona_block().lower()
        self.assertIn("overseer", persona)
        self.assertIn("orchestration", persona)
        self.assertNotIn("dark humor", persona)
        if self.orch.manifesto_path.exists():
            self.assertIn("oathweaver manifesto principles", persona)

    def test_strip_web_source_provenance_rewrites_user_provided_phrase(self) -> None:
        raw = "Based on the links you provided, this is likely current."
        cleaned = OathweaverOrchestrator._strip_web_source_provenance(raw)
        self.assertNotIn("links you provided", cleaned.lower())
        self.assertIn("based on the cited sources", cleaned.lower())

    def test_strip_web_source_provenance_drops_origin_sentence(self) -> None:
        raw = (
            "These sources were fetched autonomously by the system's web crawler — "
            "the user did NOT provide them. Here are the verified updates."
        )
        cleaned = OathweaverOrchestrator._strip_web_source_provenance(raw)
        self.assertNotIn("web crawler", cleaned.lower())
        self.assertNotIn("user did not provide", cleaned.lower())
        self.assertIn("Here are the verified updates.", cleaned)


if __name__ == "__main__":
    unittest.main()
