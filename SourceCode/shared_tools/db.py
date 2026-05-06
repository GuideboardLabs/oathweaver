from __future__ import annotations

import os
import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Iterator

_DB_ENV_VAR = "OATHWEAVER_DB_PATH"
_DEFAULT_DB_RELATIVE_PATH = Path("Runtime") / "state" / "oathweaver.db"


class OathweaverConnection(sqlite3.Connection):
    """SQLite connection that closes itself when used as a context manager."""

    def __exit__(self, exc_type, exc_value, traceback) -> bool:
        try:
            return super().__exit__(exc_type, exc_value, traceback)
        finally:
            self.close()


def resolve_repo_root(repo_root: Path | str | None = None) -> Path:
    """Resolve the repository root in a stable, testable way.

    Preference order:
    1. Explicit repo_root argument
    2. OATHWEAVER_REPO_ROOT environment override
    3. Walk up from this file location
    """
    if repo_root is not None:
        return Path(repo_root).expanduser().resolve()

    env_root = os.environ.get("OATHWEAVER_REPO_ROOT", "").strip()
    if env_root:
        return Path(env_root).expanduser().resolve()

    # SourceCode/shared_tools/db.py -> repo root is two levels up from SourceCode
    return Path(__file__).resolve().parents[2]


def resolve_db_path(repo_root: Path | str | None = None) -> Path:
    """Return the SQLite database path, honoring env overrides for local tests."""
    env_path = os.environ.get(_DB_ENV_VAR, "").strip()
    if env_path:
        path = Path(env_path).expanduser().resolve()
        path.parent.mkdir(parents=True, exist_ok=True)
        return path

    root = resolve_repo_root(repo_root)
    path = root / _DEFAULT_DB_RELATIVE_PATH
    path.parent.mkdir(parents=True, exist_ok=True)
    return path


def row_to_dict(row: sqlite3.Row | None) -> dict[str, Any] | None:
    if row is None:
        return None
    return {key: row[key] for key in row.keys()}


def connect(repo_root: Path | str | None = None, *, timeout: float = 30.0) -> sqlite3.Connection:
    """Open a Oathweaver SQLite connection with local-first defaults.

    The connection uses sqlite3.Row so callers can access columns by name.
    Autocommit mode is enabled to keep transaction boundaries explicit via
    the transaction() helper below.
    """
    db_path = resolve_db_path(repo_root)
    conn = sqlite3.connect(
        db_path,
        timeout=timeout,
        isolation_level=None,
        check_same_thread=False,
        factory=OathweaverConnection,
    )
    conn.row_factory = sqlite3.Row
    _apply_pragmas(conn)
    return conn


def _apply_pragmas(conn: sqlite3.Connection) -> None:
    conn.execute("PRAGMA journal_mode=WAL;")
    conn.execute("PRAGMA foreign_keys=ON;")
    conn.execute("PRAGMA synchronous=NORMAL;")


@contextmanager
def transaction(conn: sqlite3.Connection, *, immediate: bool = False) -> Iterator[sqlite3.Connection]:
    """Run a block inside a SQLite transaction.

    With autocommit enabled on the connection, callers get clear and explicit
    transaction control. Use immediate=True for write-heavy sections that
    should acquire the write lock up front.
    """
    begin_sql = "BEGIN IMMEDIATE;" if immediate else "BEGIN;"
    conn.execute(begin_sql)
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise


def database_exists(repo_root: Path | str | None = None) -> bool:
    return resolve_db_path(repo_root).exists()


__all__ = [
    "connect",
    "database_exists",
    "resolve_db_path",
    "resolve_repo_root",
    "row_to_dict",
    "transaction",
]
