from __future__ import annotations

import unittest

from tests.common import ROOT  # noqa: F401
from orchestrator.services.make_catalog import MAKE_CATALOG


class MakeCatalogCanonTests(unittest.TestCase):
    def test_web_app_catalog_entry_has_canon_scaffold_path(self) -> None:
        entry = MAKE_CATALOG["web_app"]
        self.assertEqual(entry.get("scaffold_path"), "canon/web_app_v1")

    def test_code_entries_include_lane_destination_and_model_lane(self) -> None:
        for make_type in ("tool", "web_app", "desktop_app"):
            with self.subTest(make_type=make_type):
                entry = MAKE_CATALOG[make_type]
                self.assertEqual(entry.get("category"), "code")
                self.assertTrue(str(entry.get("lane", "")).strip())
                self.assertTrue(str(entry.get("destination", "")).strip())
                self.assertTrue(str(entry.get("model_lane", "")).strip())

    def test_catalog_labels_are_unique(self) -> None:
        labels = [str(row.get("label", "")).strip() for row in MAKE_CATALOG.values()]
        clean = [label for label in labels if label]
        self.assertEqual(len(clean), len(set(clean)))


if __name__ == "__main__":
    unittest.main()
