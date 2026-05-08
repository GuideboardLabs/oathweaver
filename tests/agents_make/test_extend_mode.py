from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from tests.common import ROOT  # noqa: F401
from agents_make.app_pool import _enter_extend_mode, _reconcile_plumbing, _revalidate_inherited_slots
from agents_make.canon import copy_scaffold, read_slot, write_slot


class ExtendModeTests(unittest.TestCase):
    def test_extend_clears_invalid_inherited_routes_slot(self) -> None:
        with tempfile.TemporaryDirectory(prefix="extend_mode_clear_") as tmp:
            root = Path(tmp)
            prior = root / "prior"
            new = root / "new"
            copy_scaffold("web_app_v1", prior)
            # Match current marker so mode stays extend.
            (prior / ".canon-version").write_text("web_app_v1.1\n", encoding="utf-8")
            write_slot(prior / "app.py", "routes-feature", "{'/api/x': 'list_x'}", validate=False)

            mode = _enter_extend_mode(prior, new)
            self.assertEqual(mode, "extend")
            cleared = _revalidate_inherited_slots(new)
            self.assertIn("app.py/routes-feature", cleared)
            self.assertEqual(read_slot(new / "app.py", "routes-feature").strip(), "")

    def test_version_mismatch_forces_rescaffold(self) -> None:
        with tempfile.TemporaryDirectory(prefix="extend_mode_rescaffold_") as tmp:
            root = Path(tmp)
            prior = root / "prior"
            new = root / "new"
            prior.mkdir(parents=True, exist_ok=True)
            (prior / ".canon-version").write_text("web_app_v1.0\n", encoding="utf-8")

            mode = _enter_extend_mode(prior, new)
            self.assertEqual(mode, "rescaffold")
            self.assertTrue((new / "requirements.txt").exists())

    def test_reconcile_plumbing_copies_missing_static_files(self) -> None:
        with tempfile.TemporaryDirectory(prefix="extend_mode_plumbing_") as tmp:
            root = Path(tmp)
            prior = root / "prior"
            new = root / "new"
            copy_scaffold("web_app_v1", prior)
            (prior / ".canon-version").write_text("web_app_v1.1\n", encoding="utf-8")
            for name in ("requirements.txt", ".gitignore", ".env.example"):
                target = prior / name
                if target.exists():
                    target.unlink()

            mode = _enter_extend_mode(prior, new)
            self.assertEqual(mode, "extend")
            copied = _reconcile_plumbing(new)
            self.assertGreaterEqual(len(copied), 1)

    def test_extend_does_not_inherit_sqlite_runtime_artifacts(self) -> None:
        with tempfile.TemporaryDirectory(prefix="extend_mode_db_artifacts_") as tmp:
            root = Path(tmp)
            prior = root / "prior"
            new = root / "new"
            copy_scaffold("web_app_v1", prior)
            (prior / ".canon-version").write_text("web_app_v1.1\n", encoding="utf-8")
            for name in ("app.db", "app.db-wal", "app.db-shm", "app.db-journal"):
                (prior / name).write_text("stale", encoding="utf-8")

            mode = _enter_extend_mode(prior, new)
            self.assertEqual(mode, "extend")
            for name in ("app.db", "app.db-wal", "app.db-shm", "app.db-journal"):
                self.assertFalse((new / name).exists(), f"{name} should not be inherited")


if __name__ == "__main__":
    unittest.main()
