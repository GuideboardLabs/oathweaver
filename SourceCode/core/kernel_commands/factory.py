from __future__ import annotations

from pathlib import Path

from .service import KernelCommandService


def build_kernel_commands(repo_root: Path) -> KernelCommandService:
    return KernelCommandService(Path(repo_root))
