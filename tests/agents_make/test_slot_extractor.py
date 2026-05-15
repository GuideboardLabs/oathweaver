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

    def test_missing_key_without_fallback_returns_empty_string(self) -> None:
        self.assertEqual(_extract_slot_string({}, "missing"), "")

    def test_accepts_trimmed_string_values(self) -> None:
        self.assertEqual(_extract_slot_string({"slot": "  hello world  "}, "slot"), "hello world")

    def test_non_string_non_list_raises_type_error(self) -> None:
        with self.assertRaises(SlotFillTypeError):
            _extract_slot_string({"slot": 7}, "slot")


if __name__ == "__main__":
    unittest.main()
