from __future__ import annotations

import unittest
from pathlib import Path

from tests.common import ROOT


class ReadmeAccuracyTests(unittest.TestCase):
    def test_readme_mentions_current_fixed_stacks(self) -> None:
        readme = (Path(ROOT) / "README.md").read_text(encoding="utf-8")
        self.assertIn("Flask 3.x + Vue 3.5", readme)
        self.assertIn(".NET 8 + Avalonia", readme)
        self.assertIn("system-fixed", readme)

    def test_readme_mentions_stack_re_evaluation_path(self) -> None:
        readme = (Path(ROOT) / "README.md").read_text(encoding="utf-8")
        self.assertIn("Technical topic", readme)

    def test_readme_mentions_new_research_and_content_guardrails(self) -> None:
        readme = (Path(ROOT) / "README.md").read_text(encoding="utf-8")
        self.assertIn("Skeptic sidecar", readme)
        self.assertIn("Public-content guardrail", readme)
        self.assertIn("Canon v1", readme)
        self.assertIn("runtime smoke", readme)

    def test_readme_release_section_points_at_lockfile_and_changelog(self) -> None:
        readme = (Path(ROOT) / "README.md").read_text(encoding="utf-8")
        self.assertIn("requirements.lock", readme)
        self.assertIn("CHANGELOG.md", readme)


if __name__ == "__main__":
    unittest.main()
