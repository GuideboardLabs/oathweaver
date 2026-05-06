from __future__ import annotations

from pathlib import Path


def default_cag_bench_results_root(repo_root: Path) -> Path:
    """Repo-local benchmark results root used by Phase 12 command surfaces."""
    return Path(repo_root) / "Runtime" / "benchmarks" / "cag_bench" / "results"


__all__ = ["default_cag_bench_results_root"]
