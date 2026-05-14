#!/usr/bin/env bash
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$REPO_ROOT"

REQ_OUT="$REPO_ROOT/requirements.lock"
TMP_VENV="$(mktemp -d /tmp/ow-lock-venv-XXXXXX)"
TMP_DL="$(mktemp -d /tmp/ow-lock-downloads-XXXXXX)"
trap 'rm -rf "$TMP_VENV" "$TMP_DL"' EXIT

python3 -m venv "$TMP_VENV"
"$TMP_VENV/bin/pip" install -q --upgrade pip

OW_TMP_DL="$TMP_DL" OW_TMP_VENV="$TMP_VENV" "$TMP_VENV/bin/python" - <<'PY'
import os
from pathlib import Path
import hashlib
import subprocess

repo = Path.cwd()
req_path = repo / "requirements.lock"
download_dir = Path(os.environ["OW_TMP_DL"])
pip_bin = Path(os.environ["OW_TMP_VENV"]) / "bin" / "pip"

rows = [ln.strip() for ln in req_path.read_text(encoding="utf-8").splitlines() if ln.strip() and not ln.strip().startswith("#")]
requirements = [ln.split(" --hash=")[0].strip() for ln in rows if "==" in ln]

out_lines: list[str] = []
for req in requirements:
    for child in download_dir.iterdir():
        if child.is_file():
            child.unlink()
    subprocess.run(
        [str(pip_bin), "download", "--disable-pip-version-check", "--no-deps", "--dest", str(download_dir), req],
        check=True,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    artifacts = sorted(
        [p for p in download_dir.iterdir() if p.is_file()],
        key=lambda p: (0 if p.suffix == ".whl" else 1, p.name),
    )
    if not artifacts:
        raise RuntimeError(f"No artifact downloaded for {req}")
    selected = artifacts[0]
    digest = hashlib.sha256(selected.read_bytes()).hexdigest()
    out_lines.append(f"{req} --hash=sha256:{digest}")

header = [
    "# Hash-locked requirements generated for Oathweaver installers.",
    "# Regenerate via ./tools/install/regenerate_hashed_lock.sh when changing dependencies.",
    "",
]
req_path.write_text("\n".join(header + out_lines) + "\n", encoding="utf-8")
PY

echo "[OK] Wrote hash-locked requirements file: $REQ_OUT"
