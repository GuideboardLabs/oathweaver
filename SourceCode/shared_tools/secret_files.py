from __future__ import annotations

import os
from pathlib import Path


def write_secret_text(path: Path, text: str) -> None:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = target.with_suffix(target.suffix + ".tmp")
    previous_umask = os.umask(0o077)
    try:
        tmp_path.write_text(str(text), encoding="utf-8")
        os.chmod(tmp_path, 0o600)
        tmp_path.replace(target)
        os.chmod(target, 0o600)
    finally:
        os.umask(previous_umask)


def ensure_secret_mode(path: Path) -> None:
    target = Path(path)
    if not target.exists():
        return
    try:
        os.chmod(target, 0o600)
    except OSError:
        return

