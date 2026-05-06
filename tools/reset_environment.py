"""
Oathweaver Environment Reset
-----------------------------
Wipes local runtime state, with a DB-aware reset path for the new SQLite-backed
subsystems.

Examples:
  python tools/reset_environment.py --yes
  python tools/reset_environment.py --only-learning --yes
  python tools/reset_environment.py --only-learning-origin reflection --yes
  python tools/reset_environment.py --only-learning-status candidate --yes
  python tools/reset_environment.py --only-memory --yes
  python tools/reset_environment.py --full-reset --preserve-config --yes
  python tools/reset_environment.py --only-learning-origin reflection --dry-run
  python tools/reset_environment.py --report
"""

from __future__ import annotations

import argparse
import json
import shutil
import sqlite3
import sys
from dataclasses import dataclass
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
RUNTIME = ROOT / "Runtime"
PROJECTS = ROOT / "Projects"
SOURCECODE = ROOT / "SourceCode"
if str(SOURCECODE) not in sys.path:
    sys.path.insert(0, str(SOURCECODE))

from shared_tools.db import resolve_db_path  # noqa: E402
from shared_tools.feedback_learning import VALID_ORIGIN_TYPES  # noqa: E402
from shared_tools.migrations import initialize_database  # noqa: E402


RESET_TO_EMPTY_LIST: list[Path] = [
    RUNTIME / "topics" / "topics.json",
    RUNTIME / "learning" / "lessons.json",
    RUNTIME / "learning" / "reflections.json",
    RUNTIME / "routines" / "routines.json",
    RUNTIME / "watchtower" / "watches.json",
    RUNTIME / "cloud" / "pending_requests.json",
    RUNTIME / "web" / "pending_requests.json",
]

RESET_TO_EMPTY_DICT: list[Path] = [
    RUNTIME / "learning" / "continuous_improvement.json",
    RUNTIME / "memory" / "project_context.json",
    RUNTIME / "watchtower" / "briefing_state.json",
]

WIPE_DIR_CONTENTS: list[Path] = [
    RUNTIME / "conversations",
    RUNTIME / "briefings",
    RUNTIME / "activity",
    RUNTIME / "approvals" / "decided",
    RUNTIME / "approvals" / "pending",
    RUNTIME / "handoff" / "pending",
    RUNTIME / "handoff" / "denied",
    RUNTIME / "artifacts",
    RUNTIME / "logs",
    RUNTIME / "memory" / "personal",
    RUNTIME / "memory" / "projects",
    RUNTIME / "attachments",
]

HANDOFF_ROOT = RUNTIME / "handoff"
USERS_ROOT = RUNTIME / "users"
DELETE_FILES: list[Path] = [
    RUNTIME / "web" / "session_secret.txt",
    RUNTIME / "web" / "_tmp_test.txt",
    RUNTIME / "project_catalog.json",
]
TRUNCATE_JSONL: list[Path] = [
    RUNTIME / "activity" / "events.jsonl",
    RUNTIME / "cloud" / "runs.jsonl",
    RUNTIME / "web" / "sources.jsonl",
]
FAMILY_ACCOUNTS = RUNTIME / "family" / "accounts.json"
FAMILY_ACCOUNTS_EMPTY = {"accounts": [], "created_at": "", "updated_at": ""}
PROJECT_PIPELINE = RUNTIME / "project_pipeline.json"
PROJECT_PIPELINE_EMPTY = {"projects": {}}
PRESERVED_CONFIGS: list[Path] = [
    RUNTIME / "cloud" / "settings.json",
    RUNTIME / "config" / "email_config.json",
    RUNTIME / "web" / "settings.json",
]

ACTIVE = "active"
IMPORT_ONLY = "import-only"
DEAD = "dead-removable"


@dataclass(frozen=True)
class LegacyItem:
    path: str
    status: str
    owner: str
    note: str


LEGACY_RUNTIME_ITEMS: tuple[LegacyItem, ...] = (
    LegacyItem("Runtime/family/accounts.json", IMPORT_ONLY, "family_auth", "Legacy bootstrap import only. Users now live in SQLite users."),
    LegacyItem("Runtime/learning/lessons.json", IMPORT_ONLY, "feedback_learning", "Legacy fallback/reset file. Lessons now live in SQLite lessons."),
    LegacyItem("Runtime/learning/reflections.json", IMPORT_ONLY, "self_reflection", "Legacy fallback/reset file. Reflection-derived lessons now stage in SQLite."),
    LegacyItem("Runtime/memory/project_context.json", IMPORT_ONLY, "project_context_memory", "Legacy import source. Project facts now live in SQLite project_facts."),
    LegacyItem("Runtime/cloud/pending_requests.json", IMPORT_ONLY, "cloud_consult", "Legacy cloud approval queue. Pending requests now live in SQLite cloud_requests."),
    LegacyItem("Runtime/cloud/runs.jsonl", IMPORT_ONLY, "cloud_consult", "Legacy cloud audit log. Run history now lives in SQLite cloud_requests."),
    LegacyItem("Runtime/approvals/pending/", DEAD, "approval_gate", "Old filesystem approval queue. SQLite approvals is now the source of truth."),
    LegacyItem("Runtime/approvals/decided/", DEAD, "approval_gate", "Old filesystem approval archive. SQLite approvals is now the source of truth."),
    LegacyItem("Runtime/cloud/settings.json", ACTIVE, "cloud_consult", "Still active config. Keeps local cloud provider settings."),
    LegacyItem("Runtime/config/email_config.json", ACTIVE, "email_notifier", "Still active config. Email settings remain JSON-backed."),
    LegacyItem("Runtime/web/settings.json", ACTIVE, "web_gui", "Still active config. Web settings remain JSON-backed."),
    LegacyItem("Runtime/topics/topics.json", ACTIVE, "topic_engine", "Still active topic registry."),
    LegacyItem("Runtime/project_catalog.json", ACTIVE, "web_gui", "Still active catalog/summary file used by the UI."),
    LegacyItem("Runtime/project_pipeline.json", ACTIVE, "project_pipeline", "Still active project pipeline store."),
    LegacyItem("Runtime/routines/routines.json", ACTIVE, "routine_engine", "Still active routines store."),
    LegacyItem("Runtime/watchtower/watches.json", ACTIVE, "watchtower", "Still active watch list store."),
    LegacyItem("Runtime/watchtower/briefing_state.json", ACTIVE, "watchtower", "Still active watchtower checkpoint state."),
    LegacyItem("Runtime/web/pending_requests.json", ACTIVE, "web_research", "Still active web-research approval queue."),
    LegacyItem("Runtime/web/sources.jsonl", ACTIVE, "web_research", "Still active append-only source/event log."),
    LegacyItem("Runtime/activity/events.jsonl", ACTIVE, "activity_store", "Still active append-only activity log."),
)

VALID_LEARNING_STATUSES = ("candidate", "approved", "rejected", "expired")
DB_TABLES: tuple[str, ...] = (
    "lessons",
    "project_facts",
    "approvals",
    "users",
    "cloud_requests",
)


def _write_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2), encoding="utf-8")
    print(f"  reset  {path.relative_to(ROOT)}")


def _wipe_dir(path: Path) -> None:
    if not path.exists():
        return
    for child in path.iterdir():
        if child.name == ".gitkeep":
            continue
        if child.is_dir():
            shutil.rmtree(child)
        else:
            child.unlink()
    print(f"  wiped  {path.relative_to(ROOT)}/")


def _truncate_jsonl(path: Path) -> None:
    if not path.exists():
        return
    path.write_text("", encoding="utf-8")
    print(f"  clear  {path.relative_to(ROOT)}")


def _delete_file(path: Path) -> None:
    if path.exists():
        path.unlink()
        print(f"  del    {path.relative_to(ROOT)}")


def _wipe_handoff_queues() -> None:
    if not HANDOFF_ROOT.exists():
        return
    for target_dir in HANDOFF_ROOT.iterdir():
        if not target_dir.is_dir():
            continue
        for sub in ("inbox", "outbox", "outbox_processed"):
            sub_path = target_dir / sub
            if sub_path.exists():
                _wipe_dir(sub_path)


def _wipe_users() -> None:
    if not USERS_ROOT.exists():
        return
    for user_dir in USERS_ROOT.iterdir():
        if not user_dir.is_dir():
            continue
        shutil.rmtree(user_dir)
        print(f"  wiped  users/{user_dir.name}/")


def _wipe_projects() -> None:
    if not PROJECTS.exists():
        return
    for child in PROJECTS.iterdir():
        if child.name == ".gitkeep":
            continue
        if child.is_dir():
            shutil.rmtree(child)
        else:
            child.unlink()
    print("  wiped  Projects/")


def _db_exists() -> bool:
    return resolve_db_path(ROOT).exists()


def _table_exists(conn: sqlite3.Connection, table: str) -> bool:
    row = conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name = ? LIMIT 1;",
        (table,),
    ).fetchone()
    return row is not None


def _count_rows(conn: sqlite3.Connection, table: str) -> int:
    if not _table_exists(conn, table):
        return 0
    row = conn.execute(f"SELECT COUNT(*) FROM {table};").fetchone()
    return int(row[0]) if row else 0


def _db_table_counts() -> dict[str, int]:
    db_path = resolve_db_path(ROOT)
    if not db_path.exists():
        return {table: 0 for table in DB_TABLES}
    with sqlite3.connect(db_path) as conn:
        return {table: _count_rows(conn, table) for table in DB_TABLES}


def _lesson_bucket_counts() -> dict[str, dict[str, int]]:
    db_path = resolve_db_path(ROOT)
    result = {
        "by_origin": {origin: 0 for origin in sorted(VALID_ORIGIN_TYPES)},
        "by_status": {status: 0 for status in VALID_LEARNING_STATUSES},
    }
    if not db_path.exists():
        return result
    with sqlite3.connect(db_path) as conn:
        if not _table_exists(conn, "lessons"):
            return result
        for origin, count in conn.execute("SELECT origin_type, COUNT(*) FROM lessons GROUP BY origin_type;"):
            result["by_origin"][str(origin)] = int(count)
        for status, count in conn.execute("SELECT status, COUNT(*) FROM lessons GROUP BY status;"):
            result["by_status"][str(status)] = int(count)
    return result


def _approval_bucket_counts() -> dict[str, int]:
    db_path = resolve_db_path(ROOT)
    result: dict[str, int] = {}
    if not db_path.exists():
        return result
    with sqlite3.connect(db_path) as conn:
        if not _table_exists(conn, "approvals"):
            return result
        for status, count in conn.execute("SELECT status, COUNT(*) FROM approvals GROUP BY status ORDER BY status;"):
            result[str(status)] = int(count)
    return result


def _cloud_bucket_counts() -> dict[str, int]:
    db_path = resolve_db_path(ROOT)
    result: dict[str, int] = {}
    if not db_path.exists():
        return result
    with sqlite3.connect(db_path) as conn:
        if not _table_exists(conn, "cloud_requests"):
            return result
        for status, count in conn.execute("SELECT status, COUNT(*) FROM cloud_requests GROUP BY status ORDER BY status;"):
            result[str(status)] = int(count)
    return result


def _execute_db(sql: str, params: tuple = ()) -> int:
    db_path = resolve_db_path(ROOT)
    if not db_path.exists():
        return 0
    with sqlite3.connect(db_path) as conn:
        cur = conn.execute(sql, params)
        conn.commit()
        return cur.rowcount if cur.rowcount != -1 else 0


def _delete_lessons(*, origin_type: str | None = None, status: str | None = None) -> int:
    db_path = resolve_db_path(ROOT)
    if not db_path.exists():
        return 0
    clauses: list[str] = []
    params: list[str] = []
    if origin_type:
        clauses.append("origin_type = ?")
        params.append(origin_type)
    if status:
        clauses.append("status = ?")
        params.append(status)
    where_sql = f" WHERE {' AND '.join(clauses)}" if clauses else ""
    with sqlite3.connect(db_path) as conn:
        cur = conn.execute(f"DELETE FROM lessons{where_sql};", tuple(params))
        conn.commit()
        return cur.rowcount if cur.rowcount != -1 else 0


def _reset_learning_db() -> None:
    count = _delete_lessons()
    print(f"  db     cleared lessons ({count} row(s))")


def _reset_learning_by_origin(origin_type: str) -> None:
    count = _delete_lessons(origin_type=origin_type)
    print(f"  db     cleared lessons for origin={origin_type} ({count} row(s))")


def _reset_learning_by_status(status: str) -> None:
    count = _delete_lessons(status=status)
    print(f"  db     cleared lessons for status={status} ({count} row(s))")


def _reset_memory_db() -> None:
    db_path = resolve_db_path(ROOT)
    if not db_path.exists():
        return
    with sqlite3.connect(db_path) as conn:
        tables = {row[0] for row in conn.execute("SELECT name FROM sqlite_master WHERE type='table';")}
        total = 0
        for table in ("project_facts", "reflections"):
            if table in tables:
                cur = conn.execute(f"DELETE FROM {table};")
                total += cur.rowcount if cur.rowcount != -1 else 0
        conn.commit()
    print(f"  db     cleared memory tables ({total} row(s))")


def _remove_db() -> None:
    db_path = resolve_db_path(ROOT)
    wal_path = db_path.with_suffix(db_path.suffix + "-wal")
    shm_path = db_path.with_suffix(db_path.suffix + "-shm")
    for path in (db_path, wal_path, shm_path):
        if path.exists():
            path.unlink()
            print(f"  del    {path.relative_to(ROOT)}")


def _recreate_db() -> None:
    info = initialize_database(ROOT)
    print(f"  db     initialized {Path(info['db_path']).relative_to(ROOT)}")


def _print_header(args: argparse.Namespace) -> None:
    print()
    print("=== Oathweaver Environment Reset ===")
    print()
    if args.report:
        print("Mode: report")
        print("This will inspect current state and show reset impact without changing anything.")
    elif args.only_learning_origin:
        print(f"Mode: learning origin only ({args.only_learning_origin})")
        print("This will clear only lessons from the selected trust bucket.")
    elif args.only_learning_status:
        print(f"Mode: learning status only ({args.only_learning_status})")
        print("This will clear only lessons in the selected status bucket.")
    elif args.only_learning:
        print("Mode: learning only")
        print("This will clear staged/approved learning and legacy learning JSON files.")
    elif args.only_memory:
        print("Mode: memory only")
        print("This will clear project memory/context stores.")
    elif args.full_reset or not (args.only_learning or args.only_memory):
        print("Mode: full reset")
        print("This will permanently delete most local runtime state and project output.")
    print()
    if args.preserve_config:
        print("Preserving config files.")
    if args.preserve_family:
        print("Preserving family accounts and Runtime/users/.")
    if args.dry_run:
        print("Dry run only. No files or database rows will be modified.")
    print()


def _confirm(args: argparse.Namespace) -> None:
    if args.yes or args.dry_run or args.report:
        return
    answer = input("Type RESET to confirm: ").strip()
    if answer != "RESET":
        print("Aborted.")
        sys.exit(0)


def _print_legacy_cleanup_report() -> None:
    print("Legacy runtime cleanup map")
    print("--------------------------")
    grouped = {
        ACTIVE: [],
        IMPORT_ONLY: [],
        DEAD: [],
    }
    for item in LEGACY_RUNTIME_ITEMS:
        grouped[item.status].append(item)
    for status in (ACTIVE, IMPORT_ONLY, DEAD):
        print(f"{status}:")
        for item in grouped[status]:
            print(f"  - {item.path} [{item.owner}] :: {item.note}")
        print()


def _print_db_report() -> None:
    print("SQLite state report")
    print("-------------------")
    db_path = resolve_db_path(ROOT)
    print(f"DB path: {db_path.relative_to(ROOT)}")
    print(f"DB exists: {'yes' if db_path.exists() else 'no'}")
    print()
    print("Table row counts:")
    for table, count in _db_table_counts().items():
        print(f"  - {table}: {count}")
    lesson_counts = _lesson_bucket_counts()
    print()
    print("Lesson buckets by origin:")
    for origin, count in lesson_counts["by_origin"].items():
        print(f"  - {origin}: {count}")
    print()
    print("Lesson buckets by status:")
    for status, count in lesson_counts["by_status"].items():
        print(f"  - {status}: {count}")
    approvals = _approval_bucket_counts()
    if approvals:
        print()
        print("Approval buckets by status:")
        for status, count in approvals.items():
            print(f"  - {status}: {count}")
    cloud = _cloud_bucket_counts()
    if cloud:
        print()
        print("Cloud request buckets by status:")
        for status, count in cloud.items():
            print(f"  - {status}: {count}")
    print()


def _print_dry_run(args: argparse.Namespace) -> None:
    print("Dry-run impact preview")
    print("----------------------")
    if args.only_learning_origin:
        count = _lesson_bucket_counts()["by_origin"].get(args.only_learning_origin, 0)
        print(f"Would delete lessons where origin_type={args.only_learning_origin}: {count} row(s)")
    elif args.only_learning_status:
        count = _lesson_bucket_counts()["by_status"].get(args.only_learning_status, 0)
        print(f"Would delete lessons where status={args.only_learning_status}: {count} row(s)")
    elif args.only_learning:
        counts = _lesson_bucket_counts()
        total = sum(counts["by_status"].values())
        print(f"Would delete lessons: {total} row(s)")
        print("Would also reset legacy files:")
        for path in (
            RUNTIME / "learning" / "lessons.json",
            RUNTIME / "learning" / "reflections.json",
            RUNTIME / "learning" / "continuous_improvement.json",
        ):
            print(f"  - {path.relative_to(ROOT)}")
    elif args.only_memory:
        counts = _db_table_counts()
        print(f"Would delete project facts: {counts['project_facts']} row(s)")
        print("Would also wipe legacy memory directories/files:")
        for path in (
            RUNTIME / "memory" / "project_context.json",
            RUNTIME / "memory" / "personal",
            RUNTIME / "memory" / "projects",
        ):
            print(f"  - {path.relative_to(ROOT)}")
    else:
        table_counts = _db_table_counts()
        print("Would recreate the SQLite database and clear all current rows from:")
        for table, count in table_counts.items():
            print(f"  - {table}: {count}")
        print()
        print("Would reset JSON/list/dict files:")
        for path in RESET_TO_EMPTY_LIST + RESET_TO_EMPTY_DICT:
            if args.preserve_config and path in PRESERVED_CONFIGS:
                continue
            print(f"  - {path.relative_to(ROOT)}")
        print()
        print("Would wipe directories:")
        for path in WIPE_DIR_CONTENTS:
            print(f"  - {path.relative_to(ROOT)}/")
        print("  - Projects/")
        if not args.preserve_family:
            print("  - Runtime/users/")
            print(f"  - {FAMILY_ACCOUNTS.relative_to(ROOT)}")
        print()
        print("Would truncate JSONL files:")
        for path in TRUNCATE_JSONL:
            print(f"  - {path.relative_to(ROOT)}")
        print()
        print("Would delete files:")
        for path in DELETE_FILES:
            print(f"  - {path.relative_to(ROOT)}")
    print()


def _run_learning_only() -> None:
    print("Resetting learning state...")
    _reset_learning_db()
    _write_json(RUNTIME / "learning" / "lessons.json", [])
    _write_json(RUNTIME / "learning" / "reflections.json", [])
    _write_json(RUNTIME / "learning" / "continuous_improvement.json", {})


def _run_learning_origin_only(origin_type: str) -> None:
    print(f"Resetting learning state for origin={origin_type}...")
    _reset_learning_by_origin(origin_type)


def _run_learning_status_only(status: str) -> None:
    print(f"Resetting learning state for status={status}...")
    _reset_learning_by_status(status)


def _run_memory_only() -> None:
    print("Resetting memory state...")
    _reset_memory_db()
    _write_json(RUNTIME / "memory" / "project_context.json", {})
    _wipe_dir(RUNTIME / "memory" / "personal")
    _wipe_dir(RUNTIME / "memory" / "projects")


def _run_full_reset(args: argparse.Namespace) -> None:
    print("Resetting full environment...")
    for path in RESET_TO_EMPTY_LIST:
        if args.preserve_config and path in PRESERVED_CONFIGS:
            continue
        _write_json(path, [])
    for path in RESET_TO_EMPTY_DICT:
        if args.preserve_config and path in PRESERVED_CONFIGS:
            continue
        _write_json(path, {})

    if not args.preserve_family:
        _write_json(FAMILY_ACCOUNTS, FAMILY_ACCOUNTS_EMPTY)
    _write_json(PROJECT_PIPELINE, PROJECT_PIPELINE_EMPTY)

    for path in WIPE_DIR_CONTENTS:
        _wipe_dir(path)

    _wipe_dir(RUNTIME / "briefings")
    _wipe_handoff_queues()
    if not args.preserve_family:
        _wipe_users()
    _wipe_projects()

    for path in TRUNCATE_JSONL:
        _truncate_jsonl(path)
    for path in DELETE_FILES:
        _delete_file(path)

    _remove_db()
    _recreate_db()


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Reset Oathweaver local runtime state.")
    parser.add_argument("--yes", action="store_true", help="Skip confirmation prompt.")
    parser.add_argument("--dry-run", action="store_true", help="Show what would be reset without modifying anything.")
    parser.add_argument("--report", action="store_true", help="Show current SQLite counts and legacy runtime cleanup status.")
    parser.add_argument("--only-learning", action="store_true", help="Reset all learning state.")
    parser.add_argument(
        "--only-learning-origin",
        choices=sorted(VALID_ORIGIN_TYPES),
        help="Reset only lessons from one learning origin bucket.",
    )
    parser.add_argument(
        "--only-learning-status",
        choices=VALID_LEARNING_STATUSES,
        help="Reset only lessons in one learning status bucket.",
    )
    parser.add_argument("--only-memory", action="store_true", help="Reset only memory state.")
    parser.add_argument("--full-reset", action="store_true", help="Reset the full environment.")
    parser.add_argument("--preserve-family", action="store_true", help="Keep family accounts and Runtime/users/.")
    parser.add_argument("--preserve-config", action="store_true", help="Keep config files intact.")
    args = parser.parse_args()
    selected = [
        args.only_learning,
        bool(args.only_learning_origin),
        bool(args.only_learning_status),
        args.only_memory,
        args.full_reset,
    ]
    if sum(1 for item in selected if item) > 1:
        parser.error(
            "Choose at most one reset scope: --only-learning, --only-learning-origin, "
            "--only-learning-status, --only-memory, or --full-reset."
        )
    if args.report and any(selected):
        parser.error("--report cannot be combined with a reset scope.")
    return args


def run_reset() -> None:
    args = parse_args()
    _print_header(args)
    _confirm(args)
    print()

    if args.report:
        _print_db_report()
        _print_legacy_cleanup_report()
    elif args.dry_run:
        _print_dry_run(args)
    elif args.only_learning_origin:
        _run_learning_origin_only(args.only_learning_origin)
    elif args.only_learning_status:
        _run_learning_status_only(args.only_learning_status)
    elif args.only_learning:
        _run_learning_only()
    elif args.only_memory:
        _run_memory_only()
    else:
        _run_full_reset(args)

    print()
    if args.report:
        print("Report complete. No runtime state was modified.")
    elif args.dry_run:
        print("Dry run complete. No runtime state was modified.")
    else:
        print("Reset complete. Oathweaver will boot as a fresh environment for the selected scope.")
    print()


if __name__ == "__main__":
    run_reset()
