from __future__ import annotations

import unittest

from tests.common import ROOT  # noqa: F401
from benchmark.run import _benchmark_capability_score


class BenchmarkRunRegistryTests(unittest.TestCase):
    def test_capability_score_returns_weighted_quality_value(self) -> None:
        results = [
            {
                "reliability": {"good": 3, "weak": 1, "failed": 0},
                "synthesis_valid": True,
                "synthesis_sections_found": 6,
                "synthesis_sections_total": 6,
            },
            {
                "reliability": {"good": 1, "weak": 2, "failed": 1},
                "synthesis_valid": False,
                "synthesis_sections_found": 2,
                "synthesis_sections_total": 6,
            },
        ]
        score = _benchmark_capability_score(results)
        self.assertGreaterEqual(score, 0.0)
        self.assertLessEqual(score, 1.0)
        self.assertGreater(score, 0.2)


if __name__ == "__main__":
    unittest.main()
