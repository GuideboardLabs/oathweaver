from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from tests.common import ROOT  # noqa: F401
from shared_tools.document_ingestion import extract_text


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


if __name__ == "__main__":
    unittest.main()
