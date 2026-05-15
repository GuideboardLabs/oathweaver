from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from tests.common import ROOT  # noqa: F401
from shared_tools.document_ingestion import extract_text, is_document_ext, is_document_mime


class DocumentIngestionTests(unittest.TestCase):
    def test_extract_text_reads_plain_text_files(self) -> None:
        with tempfile.TemporaryDirectory(prefix="oathweaver_doc_ingest_") as tmpdir:
            path = Path(tmpdir) / "notes.txt"
            path.write_text("hello from oathweaver", encoding="utf-8")
            self.assertEqual(extract_text(path, "text/plain"), "hello from oathweaver")

    def test_extract_text_returns_empty_string_when_optional_pdf_dependency_missing(self) -> None:
        with tempfile.TemporaryDirectory(prefix="oathweaver_doc_ingest_") as tmpdir:
            path = Path(tmpdir) / "notes.pdf"
            path.write_bytes(b"%PDF-1.4\n")
            with patch("shared_tools.document_ingestion._extract_pdf", side_effect=ImportError("missing fitz")):
                self.assertEqual(extract_text(path, "application/pdf"), "")

    def test_extract_text_for_unknown_extension_fails_open(self) -> None:
        with tempfile.TemporaryDirectory(prefix="oathweaver_doc_ingest_") as tmpdir:
            path = Path(tmpdir) / "notes.unknown"
            path.write_text("fallback", encoding="utf-8")
            self.assertEqual(extract_text(path, "application/x-custom"), "")

    def test_document_type_helpers_cover_known_and_unknown_values(self) -> None:
        self.assertTrue(is_document_mime("application/pdf"))
        self.assertFalse(is_document_mime("image/png"))
        self.assertTrue(is_document_ext(".md"))
        self.assertFalse(is_document_ext(".png"))


if __name__ == "__main__":
    unittest.main()
