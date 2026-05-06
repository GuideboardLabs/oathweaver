from __future__ import annotations

import os
import shutil
import unittest
from pathlib import Path

from tests.common import ROOT, ensure_runtime


class ExternalToolsModeRouteTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        os.environ.setdefault("OATHWEAVER_OWNER_PASSWORD", "test-password")
        os.environ.setdefault("OATHWEAVER_AUTH_ENABLED", "0")
        from web_gui import app as appmod

        cls.appmod = appmod

    def setUp(self) -> None:
        self.runtime_tmp = Path(ROOT) / "Runtime" / "test_external_mode_route_tmp"
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

    def test_external_tools_mode_route_round_trip(self) -> None:
        with self.app.test_client() as client:
            response = client.post("/api/settings/external-tools-mode", json={"mode": "ask"})
            self.assertEqual(response.status_code, 200)
            payload = response.get_json()
            self.assertTrue(payload["ok"])
            self.assertEqual(payload["mode"], "ask")

            response = client.post("/api/settings/external-tools-mode", json={"mode": "off"})
            self.assertEqual(response.status_code, 200)
            payload = response.get_json()
            self.assertTrue(payload["ok"])
            self.assertEqual(payload["mode"], "off")

    def test_external_tools_mode_route_rejects_invalid_mode(self) -> None:
        with self.app.test_client() as client:
            response = client.post("/api/settings/external-tools-mode", json={"mode": "invalid"})
            self.assertEqual(response.status_code, 400)
            payload = response.get_json()
            self.assertFalse(payload["ok"])
            self.assertIn("Invalid mode", str(payload["error"]))


if __name__ == "__main__":
    unittest.main()
