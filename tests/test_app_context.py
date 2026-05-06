from __future__ import annotations

import io
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from flask import Flask

from tests.common import ensure_runtime
from shared_tools.family_auth import FamilyAuthStore
from web_gui.app_context import AppContext
from web_gui.services import ForagingManager, JobManager


class AppContextTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmpdir = tempfile.TemporaryDirectory(prefix="oathweaver_appctx_")
        self.repo_root = Path(self.tmpdir.name)
        ensure_runtime(self.repo_root)
        auth_store = FamilyAuthStore(self.repo_root)
        owner_profile = auth_store.ensure_owner("1234", "owner")
        self.ctx = AppContext(
            root=self.repo_root,
            auth_store=auth_store,
            auth_enabled=False,
            owner_profile=owner_profile,
            owner_id=str(owner_profile.get("id", "")),
            panel_cache={},
            job_manager=JobManager(),
            foraging_manager=ForagingManager(),
        )
        self.profile = self.ctx.public_profile(owner_profile) or {}

    def tearDown(self) -> None:
        self.tmpdir.cleanup()

    def test_project_catalog_round_trip(self) -> None:
        self.ctx.save_project_catalog(
            self.repo_root,
            {"oathweaver": {"description": "Main project", "updated_at": "2026-03-23T00:00:00+00:00"}},
        )
        rows = self.ctx.load_project_catalog(self.repo_root)
        self.assertEqual(rows["oathweaver"]["description"], "Main project")

    def test_save_uploaded_images_marks_missing_document_dependency(self) -> None:
        app = Flask(__name__)
        with app.test_request_context(
            "/upload",
            method="POST",
            data={"images": (io.BytesIO(b"%PDF-1.4\n"), "notes.pdf")},
            content_type="multipart/form-data",
        ):
            with patch("shared_tools.document_ingestion.extract_text", return_value=""), patch(
                "shared_tools.optional_features.feature_warning",
                return_value="missing PyMuPDF; install with `pip install -r requirements-optional-docs.txt`",
            ):
                attachments, errors = self.ctx.save_uploaded_images(self.profile, "c1")
        self.assertFalse(errors)
        self.assertEqual(len(attachments), 1)
        self.assertEqual(attachments[0]["type"], "document")
        self.assertIn("missing PyMuPDF", attachments[0]["extraction_warning"])


if __name__ == "__main__":
    unittest.main()
