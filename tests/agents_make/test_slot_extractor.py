from __future__ import annotations

import unittest

from tests.common import ROOT  # noqa: F401
from agents_make.app_pool import SlotFillTypeError, _extract_slot_string


class SlotExtractorTests(unittest.TestCase):
    def test_rejects_list(self) -> None:
        with self.assertRaises(SlotFillTypeError):
            _extract_slot_string({"routes_feature": [{"path": "/x"}]}, "routes_feature")

    def test_accepts_string(self) -> None:
        self.assertEqual(_extract_slot_string({"k": "@app.get(...)"}, "k"), "@app.get(...)")

    def test_missing_key_returns_fallback(self) -> None:
        self.assertEqual(_extract_slot_string({}, "k", fallback="x"), "x")


if __name__ == "__main__":
    unittest.main()
