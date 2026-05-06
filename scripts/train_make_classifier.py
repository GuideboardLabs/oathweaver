#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

import sys

SOURCE = ROOT / "SourceCode"
if str(SOURCE) not in sys.path:
    sys.path.insert(0, str(SOURCE))

from orchestrator.services.make_type_classifier import train_from_files


def _default_inputs(repo_root: Path) -> list[Path]:
    return [
        repo_root / "Runtime" / "training" / "make_type_seed.jsonl",
        repo_root / "Runtime" / "telemetry" / "intent_confirmer_full.jsonl",
    ]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Train Oathweaver make-type classifier.")
    parser.add_argument(
        "--repo-root",
        default=str(ROOT),
        help="Repo root (defaults to current repository).",
    )
    parser.add_argument(
        "--input",
        action="append",
        default=[],
        help="JSONL dataset path (repeatable). Defaults to seed + telemetry files.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    repo_root = Path(args.repo_root).resolve()
    inputs = [Path(p).resolve() for p in args.input] if args.input else _default_inputs(repo_root)
    artifact = train_from_files(repo_root=repo_root, input_files=inputs)
    print("make_type_classifier training complete")
    print(json.dumps({
        "artifact": str(repo_root / "Runtime" / "models" / "make_type_setfit" / "artifact.json"),
        "samples": int(artifact.get("samples", 0) or 0),
        "macro_f1": float(artifact.get("macro_f1", 0.0) or 0.0),
        "backend": str(artifact.get("backend", "keyword")),
    }, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

