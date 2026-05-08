from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path

from tests.common import ROOT  # noqa: F401
from agents_make.app_pool import _runtime_smoke_check


class AppPoolRuntimeSmokeTests(unittest.TestCase):
    def test_runtime_smoke_respects_skip_env_toggle(self) -> None:
        with tempfile.TemporaryDirectory(prefix="runtime_smoke_skip_") as tmp:
            probe_dir = Path(tmp)
            original = os.environ.get("OATHWEAVER_SKIP_RUNTIME_SMOKE")
            os.environ["OATHWEAVER_SKIP_RUNTIME_SMOKE"] = "1"
            try:
                failures = _runtime_smoke_check(probe_dir, spec=None)
            finally:
                if original is None:
                    os.environ.pop("OATHWEAVER_SKIP_RUNTIME_SMOKE", None)
                else:
                    os.environ["OATHWEAVER_SKIP_RUNTIME_SMOKE"] = original
            self.assertEqual(failures, [])


if __name__ == "__main__":
    unittest.main()
