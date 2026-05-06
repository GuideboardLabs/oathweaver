from __future__ import annotations

import shutil
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from tests.common import ensure_runtime
from shared_tools.library_service import LibraryService


class LibraryServiceTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmpdir = Path(tempfile.mkdtemp(prefix="oathweaver_library_service_"))
        ensure_runtime(self.tmpdir)
        topics_dir = self.tmpdir / "Runtime" / "topics"
        topics_dir.mkdir(parents=True, exist_ok=True)
        (topics_dir / "topics.json").write_text(
            """
[
  {
    "id": "topic_books",
    "name": "Bookshelf Notes",
    "slug": "bookshelf_notes",
    "type": "books",
    "description": "Reference topic for uploaded books, long-form reviews, and reading notes in the library system.",
    "seed_question": "What important ideas should be retained from each source?",
    "parent_id": "",
    "created_at": "2026-01-01T00:00:00+00:00",
    "updated_at": "2026-01-01T00:00:00+00:00"
  }
]
            """.strip(),
            encoding="utf-8",
        )
        self.service = LibraryService(self.tmpdir)

    def tearDown(self) -> None:
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def test_intake_and_ingest_plain_text_file_produces_markdown_and_chunks(self) -> None:
        source = self.tmpdir / "book_notes.txt"
        source.write_text(
            "Chapter 1\n\nOathweaver library notes about domain knowledge and reusable context.\n\n"
            "Chapter 2\n\nMore detail for retrieval and summaries.",
            encoding="utf-8",
        )
        item = self.service.intake_file(
            source,
            source_name="book_notes.txt",
            mime="text/plain",
            source_kind="book",
        )
        self.service._ingest_item(str(item.get("id", "")).strip())
        ready = self.service.get_item(str(item.get("id", "")).strip())
        self.assertIsNotNone(ready)
        self.assertEqual(ready["status"], "ready")
        self.assertTrue(Path(ready["markdown_path"]).exists())
        self.assertTrue(Path(ready["summary_path"]).exists())
        self.assertGreaterEqual(int(ready["chunk_count"]), 1)

    def test_duplicate_upload_reuses_existing_item(self) -> None:
        source = self.tmpdir / "repeat.txt"
        source.write_text("same content for dedupe", encoding="utf-8")
        first = self.service.intake_file(source, source_name="repeat.txt", mime="text/plain")
        second = self.service.intake_file(source, source_name="repeat.txt", mime="text/plain")
        self.assertEqual(first["id"], second["id"])
        self.assertTrue(second.get("reused"))

    def test_failed_extraction_marks_item_failed(self) -> None:
        source = self.tmpdir / "empty.pdf"
        source.write_bytes(b"%PDF-1.4\n")
        item = self.service.intake_file(
            source,
            source_name="empty.pdf",
            mime="application/pdf",
            source_kind="reference",
        )
        with patch("shared_tools.library_service.extract_text", return_value=""):
            self.service._ingest_item(str(item.get("id", "")).strip())
        failed = self.service.get_item(str(item.get("id", "")).strip())
        self.assertIsNotNone(failed)
        self.assertEqual(failed["status"], "failed")
        self.assertIn("Text extraction", failed["error_text"])

    def test_retrieve_prefers_linked_items(self) -> None:
        linked = self.tmpdir / "linked.txt"
        linked.write_text("Alpha retrieval target for oathweaver library linked topic.", encoding="utf-8")
        global_doc = self.tmpdir / "global.txt"
        global_doc.write_text("Alpha retrieval target in a global document.", encoding="utf-8")

        linked_item = self.service.intake_file(
            linked,
            source_name="linked.txt",
            mime="text/plain",
            project_slug="alpha_project",
        )
        global_item = self.service.intake_file(global_doc, source_name="global.txt", mime="text/plain")
        self.service._ingest_item(str(linked_item.get("id", "")).strip())
        self.service._ingest_item(str(global_item.get("id", "")).strip())

        rows = self.service.retrieve("alpha retrieval target", project_slug="alpha_project", limit=2)
        self.assertGreaterEqual(len(rows), 1)
        self.assertEqual(rows[0]["item_id"], linked_item["id"])

    def test_project_summary_artifact_moves_and_deletes_with_item(self) -> None:
        source = self.tmpdir / "artifact.txt"
        source.write_text("Artifact summary content for project-linked library retrieval.", encoding="utf-8")
        item = self.service.intake_file(
            source,
            source_name="artifact.txt",
            mime="text/plain",
            project_slug="alpha_project",
        )
        item_id = str(item["id"])
        self.service._ingest_item(item_id)

        alpha_dir = self.tmpdir / "Projects" / "alpha_project" / "research_summaries"
        beta_dir = self.tmpdir / "Projects" / "beta_project" / "research_summaries"
        alpha_matches = list(alpha_dir.glob(f"library__{item_id}__*.md"))
        self.assertEqual(len(alpha_matches), 1)

        updated = self.service.update_item(item_id, title="Moved Artifact", project_slug="beta_project")
        self.assertIsNotNone(updated)
        self.assertFalse(list(alpha_dir.glob(f"library__{item_id}__*.md")))
        beta_matches = list(beta_dir.glob(f"library__{item_id}__*.md"))
        self.assertEqual(len(beta_matches), 1)

        self.assertTrue(self.service.delete_item(item_id))
        self.assertFalse(list(beta_dir.glob(f"library__{item_id}__*.md")))


if __name__ == "__main__":
    unittest.main()
