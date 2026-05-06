from __future__ import annotations

import os
import shutil
import tempfile
import unittest
from pathlib import Path

from tests.common import ROOT, ensure_runtime
from bots.bot_config import load_bot_config, save_bot_config


class BotConfigStoreTests(unittest.TestCase):
    def test_load_defaults_and_round_trip(self) -> None:
        with tempfile.TemporaryDirectory(prefix="oathweaver_bot_cfg_") as tmpdir:
            repo_root = Path(tmpdir)
            ensure_runtime(repo_root)
            defaults = load_bot_config(repo_root)
            self.assertIn("telegram", defaults)
            self.assertFalse(defaults["telegram"]["enabled"])

            save_bot_config(
                repo_root,
                {
                    "telegram": {"enabled": True, "bot_token": "tg-token"},
                    "discord": {"enabled": True, "bot_token": "dc-token"},
                },
            )
            loaded = load_bot_config(repo_root)
            self.assertTrue(loaded["telegram"]["enabled"])
            self.assertEqual(loaded["discord"]["bot_token"], "dc-token")


class BotConfigRouteTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        os.environ.setdefault("OATHWEAVER_OWNER_PASSWORD", "test-password")
        os.environ.setdefault("OATHWEAVER_AUTH_ENABLED", "0")
        from web_gui import app as appmod

        cls.appmod = appmod

    def setUp(self) -> None:
        self.runtime_tmp = Path(ROOT) / "Runtime" / "test_bot_config_route_tmp"
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

    def tearDown(self) -> None:
        self.appmod.ROOT = self.original_root
        self.appmod._ensure_background_services_started = self.original_background
        shutil.rmtree(self.runtime_tmp, ignore_errors=True)

    def test_owner_bot_config_route_includes_availability_metadata(self) -> None:
        with self.app.test_client() as client:
            payload = client.get("/api/owner/bot-config").get_json()
            self.assertTrue(payload["ok"])
            self.assertIn("discord", payload["config"])
            self.assertIn("available", payload["config"]["discord"])
            self.assertIn("missing", payload["config"]["discord"])


if __name__ == "__main__":
    unittest.main()
