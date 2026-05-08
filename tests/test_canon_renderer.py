from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from tests.common import ROOT  # noqa: F401
from agents_make.canon import copy_scaffold, list_slots, read_slot, verify_plumbing_intact, write_slot


class CanonRendererTests(unittest.TestCase):
    def test_copy_and_slot_roundtrip(self) -> None:
        with tempfile.TemporaryDirectory(prefix="canon_renderer_") as tmp:
            target = Path(tmp) / "app"
            copy_scaffold("web_app_v1", target)

            marker = (target / ".canon-version").read_text(encoding="utf-8").strip()
            self.assertEqual(marker, "web_app_v1.1")

            slots = list_slots(target)
            app_slots = slots.get(target / "app.py", [])
            self.assertIn("routes-feature", app_slots)
            self.assertIn("imports-feature", app_slots)

            write_slot(target / "schema.sql", "tables", "CREATE TABLE IF NOT EXISTS example (id INTEGER PRIMARY KEY);")
            tables = read_slot(target / "schema.sql", "tables")
            self.assertIn("CREATE TABLE IF NOT EXISTS example", tables)

            self.assertEqual(verify_plumbing_intact(target, "web_app_v1"), [])

    def test_plumbing_detection_catches_non_slot_edits(self) -> None:
        with tempfile.TemporaryDirectory(prefix="canon_renderer_plumbing_") as tmp:
            target = Path(tmp) / "app"
            copy_scaffold("web_app_v1", target)
            db_path = target / "db.py"
            db_text = db_path.read_text(encoding="utf-8")
            db_path.write_text(db_text.replace("sqlite3.Row", "sqlite3.Row  # changed"), encoding="utf-8")
            divergences = verify_plumbing_intact(target, "web_app_v1")
            self.assertIn("db.py", divergences)


if __name__ == "__main__":
    unittest.main()
