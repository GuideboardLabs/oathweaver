from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from tests.common import ensure_runtime
from shared_tools.daily_digest import build_digest


class DailyDigestTests(unittest.TestCase):
    def test_build_digest_includes_watchtower_unread_line(self) -> None:
        with tempfile.TemporaryDirectory(prefix="oathweaver_digest_") as tmpdir:
            repo_root = Path(tmpdir)
            ensure_runtime(repo_root)
            with patch("web_gui.bootstrap.get_watchtower") as get_watchtower:
                get_watchtower.return_value.unread_count.return_value = 2
                digest = build_digest(repo_root)
            self.assertIn("Good morning! Here's your day", digest)
            self.assertIn("2 unread research card(s)", digest)

    def test_build_digest_returns_empty_string_on_top_level_failure(self) -> None:
        with tempfile.TemporaryDirectory(prefix="oathweaver_digest_") as tmpdir:
            repo_root = Path(tmpdir)
            with patch("shared_tools.daily_digest._build", side_effect=RuntimeError("boom")):
                self.assertEqual(build_digest(repo_root), "")


if __name__ == "__main__":
    unittest.main()
