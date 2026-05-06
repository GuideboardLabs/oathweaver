from __future__ import annotations

import os
import shutil
import unittest
from pathlib import Path

from tests.common import ROOT, ensure_runtime
from shared_tools.watchtower import WatchtowerEngine


SAMPLE_BRIEFING = """# Synthesized Research Note

## Executive Summary

Prices are stabilizing this week and lead times are improving.

## Key Findings

- Average delivery delay dropped by 12%.
- Two suppliers resumed normal capacity.
- New demand spike is concentrated in one region.

## Uncertainties & Risks

- Regional labor action could reverse progress.

## Next Steps

1. Lock two-week purchase volume.
2. Add contingency sourcing for the affected region.

Evidence Confidence: High - Multiple direct-source updates align this week.
"""


class WatchtowerResearchCardRouteTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        os.environ.setdefault("OATHWEAVER_OWNER_PASSWORD", "test-password")
        os.environ.setdefault("OATHWEAVER_AUTH_ENABLED", "0")
        from web_gui import app as appmod

        cls.appmod = appmod

    def setUp(self) -> None:
        self.runtime_tmp = Path(ROOT) / "Runtime" / "test_watchtower_research_cards"
        if self.runtime_tmp.exists():
            shutil.rmtree(self.runtime_tmp, ignore_errors=True)
        self.repo_root = self.runtime_tmp / "repo"
        self.repo_root.mkdir(parents=True, exist_ok=True)
        ensure_runtime(self.repo_root)

        self.original_root = self.appmod.ROOT
        self.original_background = self.appmod._ensure_background_services_started
        self.appmod.ROOT = self.repo_root
        self.appmod._ensure_background_services_started = lambda _app=None: None
        self.app = self.appmod.create_app()

        from infra.persistence.repositories import WatchtowerRepository

        briefings_dir = self.repo_root / "Runtime" / "briefings"
        briefings_dir.mkdir(parents=True, exist_ok=True)
        self.briefing_path = briefings_dir / "sample_watchtower_briefing.md"
        self.briefing_path.write_text(SAMPLE_BRIEFING, encoding="utf-8")

        self.repo = WatchtowerRepository(self.repo_root)
        self.repo.add_watch(
            {
                "id": "watch_test_supply",
                "topic": "Supply chain for critical parts",
                "profile": "business",
                "schedule": "daily",
                "schedule_hour": 7,
                "enabled": True,
                "last_run_at": "",
                "created_at": "2026-03-14T12:00:00+00:00",
                "updated_at": "",
            }
        )
        self.repo.save_briefing(
            {
                "id": "brief_test_supply_01",
                "watch_id": "watch_test_supply",
                "topic": "Supply chain for critical parts",
                "path": str(self.briefing_path),
                "preview": "",
                "created_at": "2026-03-14T12:05:00+00:00",
                "read": False,
            }
        )

    def tearDown(self) -> None:
        self.appmod.ROOT = self.original_root
        self.appmod._ensure_background_services_started = self.original_background
        shutil.rmtree(self.runtime_tmp, ignore_errors=True)

    def test_panel_research_cards_returns_enriched_signal_fields(self) -> None:
        with self.app.test_client() as client:
            payload = client.get("/api/panel/watchtower-research-cards?limit=20").get_json()
            rows = payload.get("research_cards", [])
            self.assertTrue(rows)
            row = rows[0]
            self.assertEqual(row.get("id"), "brief_test_supply_01")
            self.assertEqual(row.get("confidence_label"), "high")
            self.assertTrue(row.get("summary"))
            self.assertTrue(row.get("key_points"))
            self.assertTrue(row.get("next_steps"))

    def test_research_card_detail_endpoint_returns_full_markdown(self) -> None:
        with self.app.test_client() as client:
            payload = client.get("/api/watchtower/research-cards/brief_test_supply_01").get_json()
            self.assertTrue(payload.get("ok"))
            detail = payload.get("research_card", {})
            self.assertIn("content_markdown", detail)
            self.assertIn("Executive Summary", detail.get("content_markdown", ""))
            self.assertEqual(detail.get("confidence_label"), "high")

    def test_mark_unread_endpoint_round_trips_state(self) -> None:
        with self.app.test_client() as client:
            read_resp = client.post("/api/watchtower/research-cards/brief_test_supply_01/read").get_json()
            self.assertTrue(read_resp.get("ok"))
            unread_resp = client.post("/api/watchtower/research-cards/brief_test_supply_01/unread").get_json()
            self.assertTrue(unread_resp.get("ok"))
            rows = client.get("/api/panel/watchtower-research-cards?limit=20").get_json().get("research_cards", [])
            self.assertTrue(rows)
            self.assertFalse(bool(rows[0].get("read")))


class WatchtowerNoChangeGuardTests(unittest.TestCase):
    def setUp(self) -> None:
        self.runtime_tmp = Path(ROOT) / "Runtime" / "test_watchtower_no_change_guard"
        if self.runtime_tmp.exists():
            shutil.rmtree(self.runtime_tmp, ignore_errors=True)
        self.repo_root = self.runtime_tmp / "repo"
        self.repo_root.mkdir(parents=True, exist_ok=True)
        ensure_runtime(self.repo_root)
        self.engine = WatchtowerEngine(self.repo_root)

    def tearDown(self) -> None:
        shutil.rmtree(self.runtime_tmp, ignore_errors=True)

    def test_hourly_guard_skips_when_no_prior_briefing_exists(self) -> None:
        watch = {"topic": "US semiconductors", "schedule": "hourly"}
        content = (
            "# Briefing\n\n"
            "## Executive Summary\n"
            "Market chatter remains mixed.\n\n"
            "## Key Findings\n"
            "- Some discussion online, no clear primary-source confirmation.\n"
        )
        guarded = self.engine._apply_hourly_no_change_guard(watch, content, "")
        self.assertNotIn("## Material Change Check", guarded)

    def test_hourly_guard_appends_no_change_when_overlap_is_high_and_signal_is_low(self) -> None:
        watch = {"topic": "US semiconductors", "schedule": "hourly"}
        prior = (
            "# Briefing\n\n"
            "## Executive Summary\n"
            "Supply chain chatter is steady with no firm new confirmations.\n\n"
            "## Key Findings\n"
            "- Industry forums repeated prior rumors.\n"
            "Evidence Confidence: Low - mostly repeated social chatter.\n"
        )
        current = (
            "# Briefing\n\n"
            "## Executive Summary\n"
            "Supply chain chatter is steady with no firm new confirmations.\n\n"
            "## Key Findings\n"
            "- Industry forums repeated prior rumors.\n"
            "Evidence Confidence: Low - mostly repeated social chatter.\n"
        )
        guarded = self.engine._apply_hourly_no_change_guard(watch, current, prior)
        self.assertIn("## Material Change Check", guarded)
        self.assertIn("No material changes since last run", guarded)
        self.assertIn("Evidence overlap with prior briefing:", guarded)

    def test_hourly_guard_does_not_append_when_update_is_distinct(self) -> None:
        watch = {"topic": "US semiconductors", "schedule": "hourly"}
        prior = (
            "# Briefing\n\n"
            "## Executive Summary\n"
            "No confirmed updates in the prior hour.\n\n"
            "## Key Findings\n"
            "- Rumors persisted with low confidence.\n"
            "Evidence Confidence: Low - no corroborated sources.\n"
        )
        current = (
            "# Briefing\n\n"
            "## Executive Summary\n"
            "A major supplier confirmed a verified output expansion this hour.\n\n"
            "## Key Findings\n"
            "- The supplier published a formal production update.\n"
            "- Two downstream buyers confirmed receipt scheduling changes.\n"
            "Evidence Confidence: High - direct statements from primary sources.\n"
        )
        guarded = self.engine._apply_hourly_no_change_guard(watch, current, prior)
        self.assertNotIn("## Material Change Check", guarded)


if __name__ == "__main__":
    unittest.main()
