from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from tests.common import ROOT  # noqa: F401
from core.capability_registry import CapabilityRegistry


class CapabilityRegistryReaderTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory(prefix="cap_registry_reader_")
        self.repo_root = Path(self.tmp.name)
        self.registry = CapabilityRegistry(self.repo_root)

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def test_list_recent_claims_returns_newest_first(self) -> None:
        claims_path = self.repo_root / "Runtime" / "capability_registry" / "claims.json"
        claims_path.write_text(
            json.dumps(
                [
                    {"claim": "older", "created_at": "2026-05-01T00:00:00+00:00", "benchmarks": ["a"]},
                    {"claim": "newer", "created_at": "2026-05-03T00:00:00+00:00", "benchmarks": ["b"]},
                ],
                ensure_ascii=True,
            ),
            encoding="utf-8",
        )

        rows = self.registry.list_recent_claims(limit=5)

        self.assertEqual(rows[0]["claim"], "newer")
        self.assertEqual(rows[1]["claim"], "older")

    def test_list_recent_claims_respects_limit(self) -> None:
        claims_path = self.repo_root / "Runtime" / "capability_registry" / "claims.json"
        claims_path.write_text(
            json.dumps(
                [
                    {"claim": "c1", "created_at": "2026-05-01T00:00:00+00:00"},
                    {"claim": "c2", "created_at": "2026-05-02T00:00:00+00:00"},
                    {"claim": "c3", "created_at": "2026-05-03T00:00:00+00:00"},
                ],
                ensure_ascii=True,
            ),
            encoding="utf-8",
        )

        rows = self.registry.list_recent_claims(limit=2)

        self.assertEqual(len(rows), 2)
        self.assertEqual([row["claim"] for row in rows], ["c3", "c2"])

    def test_list_recent_claims_missing_or_invalid_file_returns_empty(self) -> None:
        claims_path = self.repo_root / "Runtime" / "capability_registry" / "claims.json"
        claims_path.unlink(missing_ok=True)
        self.assertEqual(self.registry.list_recent_claims(), [])

        claims_path.write_text('{"broken": true}', encoding="utf-8")
        self.assertEqual(self.registry.list_recent_claims(), [])


if __name__ == "__main__":
    unittest.main()
