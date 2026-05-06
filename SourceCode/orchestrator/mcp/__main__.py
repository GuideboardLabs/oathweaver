from __future__ import annotations

import argparse
from pathlib import Path

from .server import run_http, run_stdio


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run Oathweaver MCP server.")
    parser.add_argument("--repo-root", default=str(Path(__file__).resolve().parents[3]))
    parser.add_argument("--transport", choices=["stdio", "http"], default="stdio")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=9876)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    repo_root = Path(args.repo_root).resolve()
    if args.transport == "http":
        run_http(repo_root, host=args.host, port=args.port)
        return
    run_stdio(repo_root)


if __name__ == "__main__":
    main()

