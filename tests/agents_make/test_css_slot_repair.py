from __future__ import annotations

import unittest

from tests.common import ROOT  # noqa: F401
from agents_make.app_pool import _replace_raw_hex_with_neu_vars
from agents_make.canon.slot_validators import validate_slot


class CssSlotRepairTests(unittest.TestCase):
    def test_replaces_raw_hex_colors_with_neu_tokens(self) -> None:
        css = """
.card {
  color: #ffffff;
  background: #1f2937;
  border: 1px solid #334155;
}
""".strip()
        repaired = _replace_raw_hex_with_neu_vars(css)
        self.assertNotRegex(repaired, r"#[0-9a-fA-F]{3,8}\\b")
        self.assertIn("var(--neu-", repaired)

    def test_repaired_css_passes_feature_styles_validator(self) -> None:
        css = ".hero { background: #0ea5e9; color: #111827; }"
        repaired = _replace_raw_hex_with_neu_vars(css)
        violations = validate_slot("static/styles.css", "feature-styles", repaired)
        self.assertFalse(any(v.rule == "raw_hex_color" for v in violations))
        self.assertEqual(violations, [])


if __name__ == "__main__":
    unittest.main()
