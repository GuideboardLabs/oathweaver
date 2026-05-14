from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable, Sequence

from shared_tools.db import connect, resolve_db_path, row_to_dict, transaction


MigrationFn = Callable[[sqlite3.Connection], None]


@dataclass(frozen=True)
class Migration:
    version: int
    name: str
    apply: MigrationFn


SCHEMA_MIGRATIONS_SQL = """
CREATE TABLE IF NOT EXISTS schema_migrations (
    version INTEGER PRIMARY KEY,
    name TEXT NOT NULL,
    applied_at TEXT NOT NULL
);
""".strip()


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _migration_001_baseline(conn: sqlite3.Connection) -> None:
    # Intentional baseline. It proves the DB is initialized and gives us a
    # stable starting point for later subsystem tables.
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS app_meta (
            key TEXT PRIMARY KEY,
            value TEXT NOT NULL,
            updated_at TEXT NOT NULL
        );
        """.strip()
    )
    conn.execute(
        """
        INSERT INTO app_meta(key, value, updated_at)
        VALUES (?, ?, ?)
        ON CONFLICT(key) DO UPDATE SET
            value = excluded.value,
            updated_at = excluded.updated_at;
        """.strip(),
        ("schema_baseline", "v1", _now_iso()),
    )


def _migration_002_lessons(conn: sqlite3.Connection) -> None:
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS lessons (
            id TEXT PRIMARY KEY,
            lane TEXT NOT NULL,
            project TEXT,
            summary TEXT NOT NULL,
            guidance TEXT NOT NULL,
            origin_type TEXT NOT NULL,
            source TEXT NOT NULL,
            status TEXT NOT NULL,
            confidence REAL NOT NULL DEFAULT 0.5,
            active INTEGER NOT NULL DEFAULT 0,
            approved_by TEXT,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            expires_at TEXT
        );
        """.strip()
    )
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_lessons_lane_status_active ON lessons(lane, status, active);"
    )
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_lessons_project_lane ON lessons(project, lane);"
    )
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_lessons_active_expiry ON lessons(active, expires_at);"
    )


def _migration_003_project_facts(conn: sqlite3.Connection) -> None:
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS project_facts (
            project_slug TEXT NOT NULL,
            fact_key TEXT NOT NULL,
            fact_value TEXT NOT NULL,
            source TEXT,
            updated_at TEXT NOT NULL,
            PRIMARY KEY (project_slug, fact_key)
        );
        """.strip()
    )
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_project_facts_project_updated ON project_facts(project_slug, updated_at);"
    )


def _migration_004_approvals(conn: sqlite3.Connection) -> None:
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS approvals (
            id TEXT PRIMARY KEY,
            record_type TEXT NOT NULL,
            lane TEXT NOT NULL,
            project TEXT,
            title TEXT,
            text TEXT NOT NULL,
            action_type TEXT,
            action_payload_json TEXT,
            source TEXT,
            status TEXT NOT NULL,
            created_at TEXT NOT NULL,
            decided_at TEXT,
            decision_reason TEXT
        );
        """.strip()
    )
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_approvals_status_created ON approvals(status, created_at);"
    )
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_approvals_record_status ON approvals(record_type, status, created_at);"
    )
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_approvals_project_lane ON approvals(project, lane);"
    )


def _migration_005_users(conn: sqlite3.Connection) -> None:
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS users (
            id TEXT PRIMARY KEY,
            username TEXT NOT NULL UNIQUE,
            display_name TEXT NOT NULL,
            role TEXT NOT NULL,
            color TEXT NOT NULL,
            password_hash TEXT NOT NULL,
            password_salt TEXT NOT NULL,
            is_owner INTEGER NOT NULL DEFAULT 0,
            active INTEGER NOT NULL DEFAULT 1,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        );
        """.strip()
    )
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_users_active_owner ON users(active, is_owner, username);"
    )


def _migration_008_cloud_requests(conn: sqlite3.Connection) -> None:
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS cloud_requests (
            id TEXT PRIMARY KEY,
            project TEXT,
            lane TEXT,
            mode TEXT NOT NULL,
            purpose TEXT NOT NULL,
            request_payload_json TEXT NOT NULL,
            response_json TEXT,
            status TEXT NOT NULL,
            created_at TEXT NOT NULL,
            completed_at TEXT
        );
        """.strip()
    )
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_cloud_requests_status_created ON cloud_requests(status, created_at);"
    )
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_cloud_requests_project_created ON cloud_requests(project, created_at);"
    )
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_cloud_requests_mode_status ON cloud_requests(mode, status, created_at);"
    )


def _migration_009_workspace_actions(conn: sqlite3.Connection) -> None:
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS workspace_actions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            project TEXT NOT NULL,
            action_kind TEXT NOT NULL,
            path TEXT NOT NULL,
            status TEXT NOT NULL,
            detail TEXT NOT NULL DEFAULT '',
            created_at TEXT NOT NULL
        );
        """.strip()
    )
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_workspace_actions_project_created ON workspace_actions(project, created_at);"
    )
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_workspace_actions_kind_status ON workspace_actions(action_kind, status, created_at);"
    )


def _migration_010_project_pipeline_states(conn: sqlite3.Connection) -> None:
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS project_pipeline_states (
            project_slug TEXT PRIMARY KEY,
            mode TEXT NOT NULL,
            target TEXT NOT NULL,
            topic_type TEXT NOT NULL,
            updated_at TEXT NOT NULL
        );
        """.strip()
    )
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_project_pipeline_mode_updated ON project_pipeline_states(mode, updated_at);"
    )


def _migration_011_watchtower_state(conn: sqlite3.Connection) -> None:
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS watchtower_watches (
            id TEXT PRIMARY KEY,
            topic TEXT NOT NULL,
            profile TEXT NOT NULL,
            schedule TEXT NOT NULL,
            schedule_hour INTEGER NOT NULL DEFAULT 7,
            enabled INTEGER NOT NULL DEFAULT 1,
            last_run_at TEXT NOT NULL DEFAULT '',
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL DEFAULT ''
        );
        """.strip()
    )
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_watchtower_watches_enabled_schedule ON watchtower_watches(enabled, schedule, schedule_hour);"
    )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS watchtower_briefings (
            id TEXT PRIMARY KEY,
            watch_id TEXT NOT NULL DEFAULT '',
            topic TEXT NOT NULL DEFAULT '',
            path TEXT NOT NULL DEFAULT '',
            preview TEXT NOT NULL DEFAULT '',
            created_at TEXT NOT NULL,
            is_read INTEGER NOT NULL DEFAULT 0
        );
        """.strip()
    )
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_watchtower_briefings_read_created ON watchtower_briefings(is_read, created_at);"
    )


def _migration_012_job_state(conn: sqlite3.Connection) -> None:
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS job_runs (
            profile_id TEXT NOT NULL,
            request_id TEXT NOT NULL,
            conversation_id TEXT NOT NULL DEFAULT '',
            mode TEXT NOT NULL DEFAULT 'command',
            project TEXT NOT NULL DEFAULT '',
            lane TEXT NOT NULL DEFAULT '',
            status TEXT NOT NULL DEFAULT 'running',
            stage TEXT NOT NULL DEFAULT 'queued',
            started_at TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            cancel_requested INTEGER NOT NULL DEFAULT 0,
            cancel_requested_at TEXT NOT NULL DEFAULT '',
            summary_path TEXT NOT NULL DEFAULT '',
            raw_path TEXT NOT NULL DEFAULT '',
            web_stack_json TEXT NOT NULL DEFAULT '{}',
            agent_tracker_json TEXT NOT NULL DEFAULT '{}',
            user_text_preview TEXT NOT NULL DEFAULT '',
            PRIMARY KEY (profile_id, request_id)
        );
        """.strip()
    )
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_job_runs_profile_status_updated ON job_runs(profile_id, status, updated_at DESC);"
    )
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_job_runs_conversation_updated ON job_runs(conversation_id, updated_at DESC);"
    )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS job_events (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            profile_id TEXT NOT NULL,
            request_id TEXT NOT NULL,
            ts TEXT NOT NULL,
            stage TEXT NOT NULL,
            detail TEXT NOT NULL DEFAULT ''
        );
        """.strip()
    )
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_job_events_profile_request_ts ON job_events(profile_id, request_id, id DESC);"
    )


_MIGRATION_IDENTIFIER_TABLES = frozenset(
    {
        "app_meta",
        "lessons",
        "project_facts",
        "approvals",
        "users",
        "cloud_requests",
        "workspace_actions",
        "project_pipeline_states",
        "watchtower_watches",
        "watchtower_briefings",
        "job_runs",
        "job_events",
        "domain_reputation",
        "forage_cards",
        "bot_user_mappings",
        "library_items",
        "library_chunks",
        "web_cache_chunks",
    }
)


def _safe_identifier_table(table: str) -> str:
    key = str(table or "").strip()
    if key not in _MIGRATION_IDENTIFIER_TABLES:
        raise ValueError(f"Unsupported migration table identifier: {key!r}")
    return key


def _column_exists(conn: sqlite3.Connection, table: str, column: str) -> bool:
    safe_table = _safe_identifier_table(table)
    rows = conn.execute(f"PRAGMA table_info({safe_table});").fetchall()
    target = str(column or "").strip().lower()
    for row in rows:
        try:
            name = str(row[1]).strip().lower()
        except Exception:
            name = ""
        if name == target:
            return True
    return False


def _add_column_if_missing(conn: sqlite3.Connection, table: str, definition: str, column: str) -> None:
    if _column_exists(conn, table, column):
        return
    safe_table = _safe_identifier_table(table)
    conn.execute(f"ALTER TABLE {safe_table} ADD COLUMN {definition};")


def _migration_014_domain_reputation(conn: sqlite3.Connection) -> None:
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS domain_reputation (
            domain TEXT PRIMARY KEY,
            adjustment REAL NOT NULL DEFAULT 0.0,
            query_count INTEGER NOT NULL DEFAULT 0,
            correction_count INTEGER NOT NULL DEFAULT 0,
            updated_at TEXT NOT NULL
        );
        """.strip()
    )
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_domain_reputation_adjustment ON domain_reputation(adjustment);"
    )


def _migration_015_forage_cards(conn: sqlite3.Connection) -> None:
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS forage_cards (
            id TEXT PRIMARY KEY,
            title TEXT NOT NULL DEFAULT '',
            project TEXT NOT NULL DEFAULT '',
            summary_path TEXT NOT NULL DEFAULT '',
            raw_path TEXT NOT NULL DEFAULT '',
            query TEXT NOT NULL DEFAULT '',
            preview TEXT NOT NULL DEFAULT '',
            source_count INTEGER NOT NULL DEFAULT 0,
            is_pinned INTEGER NOT NULL DEFAULT 0,
            is_read INTEGER NOT NULL DEFAULT 0,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL DEFAULT ''
        );
        """.strip()
    )
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_forage_cards_created "
        "ON forage_cards(is_pinned DESC, created_at DESC);"
    )


def _migration_016_bot_user_mappings(conn: sqlite3.Connection) -> None:
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS bot_user_mappings (
            id TEXT PRIMARY KEY,
            platform TEXT NOT NULL,
            platform_user_id TEXT NOT NULL,
            platform_username TEXT NOT NULL,
            oathweaver_user_id TEXT NOT NULL,
            conversation_id TEXT NOT NULL,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            UNIQUE(platform, platform_user_id)
        );
        """.strip()
    )
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_bot_user_platform "
        "ON bot_user_mappings(platform, platform_user_id);"
    )


def _migration_017_library_tables(conn: sqlite3.Connection) -> None:
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS library_items (
            id TEXT PRIMARY KEY,
            title TEXT NOT NULL DEFAULT '',
            source_name TEXT NOT NULL DEFAULT '',
            source_kind TEXT NOT NULL DEFAULT 'general',
            mime TEXT NOT NULL DEFAULT '',
            ext TEXT NOT NULL DEFAULT '',
            file_size INTEGER NOT NULL DEFAULT 0,
            content_hash TEXT NOT NULL DEFAULT '',
            source_path TEXT NOT NULL DEFAULT '',
            markdown_path TEXT NOT NULL DEFAULT '',
            summary_path TEXT NOT NULL DEFAULT '',
            topic_id TEXT NOT NULL DEFAULT '',
            project_slug TEXT NOT NULL DEFAULT '',
            status TEXT NOT NULL DEFAULT 'queued',
            error_text TEXT NOT NULL DEFAULT '',
            source_origin TEXT NOT NULL DEFAULT 'manual_upload',
            conversation_id TEXT NOT NULL DEFAULT '',
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            ingested_at TEXT NOT NULL DEFAULT ''
        );
        """.strip()
    )
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_library_items_status_created "
        "ON library_items(status, created_at DESC);"
    )
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_library_items_hash "
        "ON library_items(content_hash, updated_at DESC);"
    )
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_library_items_topic_project "
        "ON library_items(topic_id, project_slug, updated_at DESC);"
    )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS library_chunks (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            item_id TEXT NOT NULL,
            chunk_index INTEGER NOT NULL,
            heading TEXT NOT NULL DEFAULT '',
            chunk_text TEXT NOT NULL DEFAULT '',
            embedding_json TEXT NOT NULL DEFAULT '',
            token_count INTEGER NOT NULL DEFAULT 0,
            char_count INTEGER NOT NULL DEFAULT 0,
            created_at TEXT NOT NULL,
            FOREIGN KEY(item_id) REFERENCES library_items(id) ON DELETE CASCADE
        );
        """.strip()
    )
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_library_chunks_item "
        "ON library_chunks(item_id, chunk_index ASC);"
    )


def _migration_018_web_cache_chunks(conn: sqlite3.Connection) -> None:
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS web_cache_chunks (
            id TEXT PRIMARY KEY,
            project TEXT NOT NULL DEFAULT '',
            url TEXT NOT NULL DEFAULT '',
            title TEXT NOT NULL DEFAULT '',
            domain TEXT NOT NULL DEFAULT '',
            snippet TEXT NOT NULL DEFAULT '',
            source_score REAL NOT NULL DEFAULT 0.0,
            source_tier TEXT NOT NULL DEFAULT 'tier3',
            crawled_at TEXT NOT NULL,
            expires_at TEXT NOT NULL
        );
        """.strip()
    )
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_web_cache_chunks_project_expires "
        "ON web_cache_chunks(project, expires_at DESC);"
    )
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_web_cache_chunks_url "
        "ON web_cache_chunks(url, crawled_at DESC);"
    )


def _migration_019_library_domain(conn: sqlite3.Connection) -> None:
    try:
        conn.execute("ALTER TABLE library_items ADD COLUMN domain TEXT NOT NULL DEFAULT '';")
    except Exception:
        pass
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_library_items_domain "
        "ON library_items(domain, updated_at DESC);"
    )


def _migration_020_drop_unused_tables(conn: sqlite3.Connection) -> None:
    conn.execute("DROP TABLE IF EXISTS cloud_requests;")
    conn.execute("DROP TABLE IF EXISTS app_meta;")


MIGRATIONS: Sequence[Migration] = (
    Migration(version=1, name="baseline_app_meta", apply=_migration_001_baseline),
    Migration(version=2, name="lessons_table", apply=_migration_002_lessons),
    Migration(version=3, name="project_facts_table", apply=_migration_003_project_facts),
    Migration(version=4, name="approvals_table", apply=_migration_004_approvals),
    Migration(version=5, name="users_table", apply=_migration_005_users),
    Migration(version=8, name="cloud_requests_table", apply=_migration_008_cloud_requests),
    Migration(version=9, name="workspace_actions_table", apply=_migration_009_workspace_actions),
    Migration(version=10, name="project_pipeline_state_table", apply=_migration_010_project_pipeline_states),
    Migration(version=11, name="watchtower_state_tables", apply=_migration_011_watchtower_state),
    Migration(version=12, name="job_state_tables", apply=_migration_012_job_state),
    Migration(version=14, name="domain_reputation_table", apply=_migration_014_domain_reputation),
    Migration(version=15, name="forage_cards_table", apply=_migration_015_forage_cards),
    Migration(version=16, name="bot_user_mappings_table", apply=_migration_016_bot_user_mappings),
    Migration(version=17, name="library_tables", apply=_migration_017_library_tables),
    Migration(version=18, name="web_cache_chunks", apply=_migration_018_web_cache_chunks),
    Migration(version=19, name="library_domain_column", apply=_migration_019_library_domain),
    Migration(version=20, name="drop_unused_tables", apply=_migration_020_drop_unused_tables),
)


def ensure_migration_table(conn: sqlite3.Connection) -> None:
    conn.execute(SCHEMA_MIGRATIONS_SQL)


def get_applied_versions(conn: sqlite3.Connection) -> set[int]:
    ensure_migration_table(conn)
    rows = conn.execute("SELECT version FROM schema_migrations ORDER BY version ASC;").fetchall()
    return {int(row["version"]) for row in rows}


def get_status(conn: sqlite3.Connection) -> list[dict[str, object]]:
    ensure_migration_table(conn)
    rows = conn.execute(
        "SELECT version, name, applied_at FROM schema_migrations ORDER BY version ASC;"
    ).fetchall()
    return [row_to_dict(row) or {} for row in rows]


def apply_pending_migrations(conn: sqlite3.Connection) -> list[int]:
    ensure_migration_table(conn)
    applied_versions = get_applied_versions(conn)
    applied_now: list[int] = []

    for migration in MIGRATIONS:
        if migration.version in applied_versions:
            continue
        with transaction(conn, immediate=True):
            migration.apply(conn)
            conn.execute(
                "INSERT INTO schema_migrations(version, name, applied_at) VALUES (?, ?, ?);",
                (migration.version, migration.name, _now_iso()),
            )
        applied_now.append(migration.version)
        applied_versions.add(migration.version)

    return applied_now


def initialize_database(repo_root: Path | str | None = None) -> dict[str, object]:
    db_path = resolve_db_path(repo_root)
    with connect(repo_root) as conn:
        ensure_migration_table(conn)
        applied = apply_pending_migrations(conn)
        status = get_status(conn)
    return {
        "db_path": str(db_path),
        "applied_versions": applied,
        "current_version": max((m.version for m in MIGRATIONS), default=0),
        "status": status,
    }


__all__ = [
    "MIGRATIONS",
    "Migration",
    "apply_pending_migrations",
    "ensure_migration_table",
    "get_applied_versions",
    "get_status",
    "initialize_database",
]
