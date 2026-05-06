import argparse
import json
import time
from pathlib import Path


def format_row(row: dict) -> str:
    ts = row.get("ts", "")
    actor = row.get("actor", "unknown")
    event = row.get("event", "event")
    details = row.get("details", {})
    return f"[{ts}] {actor:<14} {event:<20} {details}"


def read_rows(path: Path) -> list[dict]:
    if not path.exists():
        return []
    rows: list[dict] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            rows.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return rows


def main() -> None:
    parser = argparse.ArgumentParser(description="Oathweaver activity viewer")
    parser.add_argument("--follow", action="store_true", help="Follow new events")
    parser.add_argument("--limit", type=int, default=30, help="How many recent events to print")
    args = parser.parse_args()

    repo_root = Path(__file__).resolve().parents[2]
    path = repo_root / "Runtime" / "activity" / "events.jsonl"

    seen = 0
    rows = read_rows(path)
    for row in rows[-args.limit :]:
        print(format_row(row))
    seen = len(rows)

    if not args.follow:
        return

    while True:
        time.sleep(1.0)
        rows = read_rows(path)
        if len(rows) > seen:
            for row in rows[seen:]:
                print(format_row(row))
            seen = len(rows)


if __name__ == "__main__":
    main()
