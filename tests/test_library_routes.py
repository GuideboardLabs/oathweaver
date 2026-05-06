from __future__ import annotations

import io
import os
import shutil
import time
import unittest
from pathlib import Path

from tests.common import ROOT, ensure_runtime


class LibraryRouteTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        os.environ.setdefault("OATHWEAVER_OWNER_PASSWORD", "test-password")
        os.environ.setdefault("OATHWEAVER_AUTH_ENABLED", "0")
        from web_gui import app as appmod

        cls.appmod = appmod

    def setUp(self) -> None:
        self.runtime_tmp = Path(ROOT) / "Runtime" / "test_library_routes_tmp"
        if self.runtime_tmp.exists():
            shutil.rmtree(self.runtime_tmp, ignore_errors=True)
        self.repo_root = self.runtime_tmp / "repo"
        self.repo_root.mkdir(parents=True, exist_ok=True)
        ensure_runtime(self.repo_root)
        topics_dir = self.repo_root / "Runtime" / "topics"
        topics_dir.mkdir(parents=True, exist_ok=True)
        (topics_dir / "topics.json").write_text(
            """
[
  {
    "id": "topic_library",
    "name": "Library Topic",
    "slug": "library_topic",
    "type": "books",
    "description": "Topic used by tests to link uploaded library items with a named knowledge domain.",
    "seed_question": "How should uploaded documents be organized?",
    "parent_id": "",
    "created_at": "2026-01-01T00:00:00+00:00",
    "updated_at": "2026-01-01T00:00:00+00:00"
  }
]
            """.strip(),
            encoding="utf-8",
        )

        self.original_root = self.appmod.ROOT
        self.original_background = self.appmod._ensure_background_services_started
        self.appmod.ROOT = self.repo_root
        self.appmod._ensure_background_services_started = lambda _app=None: None
        self.app = self.appmod.create_app()

    def tearDown(self) -> None:
        self.appmod.ROOT = self.original_root
        self.appmod._ensure_background_services_started = self.original_background
        shutil.rmtree(self.runtime_tmp, ignore_errors=True)

    def _wait_for_item(self, client, item_id: str, *, timeout_sec: float = 30.0) -> dict:
        deadline = time.time() + timeout_sec
        last_payload = {}
        while time.time() < deadline:
            resp = client.get(f"/api/library/{item_id}")
            last_payload = resp.get_json() or {}
            item = last_payload.get("item") or {}
            if item.get("status") in {"ready", "failed"}:
                return item
            time.sleep(0.1)
        return last_payload.get("item") or {}

    def test_intake_route_creates_item_and_panel_lists_it(self) -> None:
        with self.app.test_client() as client:
            response = client.post(
                "/api/library/intake",
                data={
                    "source_kind": "book",
                    "topic_id": "topic_library",
                    "files": (io.BytesIO(b"Library route content for oathweaver."), "route_notes.txt"),
                },
                content_type="multipart/form-data",
            )
            self.assertEqual(response.status_code, 201)
            payload = response.get_json()
            self.assertTrue(payload["items"])
            item_id = payload["items"][0]["id"]

            item = self._wait_for_item(client, item_id)
            self.assertEqual(item.get("status"), "ready")
            self.assertTrue(Path(item["markdown_path"]).exists())
            self.assertTrue(Path(item["summary_path"]).exists())

            panel = client.get("/api/panel/library").get_json()
            self.assertTrue(panel["items"])
            self.assertGreaterEqual(int(panel["counts"]["total"]), 1)
            self.assertTrue(any(row["id"] == item_id for row in panel["items"]))

    def test_library_detail_markdown_and_source_routes_work(self) -> None:
        with self.app.test_client() as client:
            response = client.post(
                "/api/library/intake",
                data={
                    "source_kind": "reference",
                    "files": (io.BytesIO(b"Reference details for markdown and source access."), "reference.txt"),
                },
                content_type="multipart/form-data",
            )
            self.assertEqual(response.status_code, 201)
            item_id = response.get_json()["items"][0]["id"]
            item = self._wait_for_item(client, item_id)
            self.assertEqual(item.get("status"), "ready")

            detail = client.get(f"/api/library/{item_id}").get_json()
            self.assertEqual(detail["item"]["id"], item_id)

            markdown = client.get(f"/api/library/{item_id}/markdown").get_json()
            self.assertIn("#", markdown["content"])

            source_response = client.get(f"/api/library/{item_id}/source")
            self.assertEqual(source_response.status_code, 200)
            source_response.close()


if __name__ == "__main__":
    unittest.main()
