from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from tests.common import ROOT  # noqa: F401
from orchestrator.services.make_type_classifier import classify, train


class MakeTypeClassifierTests(unittest.TestCase):
    def test_keyword_training_and_classification(self) -> None:
        with tempfile.TemporaryDirectory(prefix="oathweaver_make_cls_") as tmpdir:
            root = Path(tmpdir)
            out_dir = root / "Runtime" / "models" / "make_type_setfit"
            rows = [
                ("write a warm outreach email to a customer", "email"),
                ("draft a product launch email sequence", "email"),
                ("build a lightweight web app for notes", "web_app"),
                ("create a responsive web app landing page", "web_app"),
            ]
            artifact = train(rows, out_dir=out_dir)
            self.assertGreaterEqual(int(artifact.get("samples", 0) or 0), 4)

            label, confidence = classify("please write an email follow-up", repo_root=root)
            self.assertEqual(label, "email")
            self.assertGreater(confidence, 0.0)


if __name__ == "__main__":
    unittest.main()
