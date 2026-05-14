from __future__ import annotations

import argparse
from pathlib import Path

from .server import create_openai_compatible_app


def main() -> None:
    parser = argparse.ArgumentParser(prog="oathweaver-api", description="Oathweaver unified API server")
    parser.add_argument("--repo-root", default=str(Path(__file__).resolve().parents[3]))
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=11435)
    args = parser.parse_args()

    app = create_openai_compatible_app(Path(args.repo_root).resolve(), bind_host=str(args.host))
    app.run(host=str(args.host), port=int(args.port), debug=False)


if __name__ == "__main__":
    main()
