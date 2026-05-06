from __future__ import annotations

"""
Learned source reputation.
Tracks per-domain adjustment scores that modify source authority over time.
- record_success: source was used in a completed research result (+0.01 recovery, max 0.0)
- record_correction: source contributed to incorrect/flagged output (-0.05, clamped to -0.3)
Adjustments are small and compound over sessions so they don't dominate tier scores.
"""

import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


class DomainReputation:
    def __init__(self, repo_root: Path | str) -> None:
        self.repo_root = Path(repo_root)
        self._db_path = self.repo_root / "Runtime" / "state" / "oathweaver.db"

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(str(self._db_path), timeout=10)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL;")
        conn.execute("PRAGMA foreign_keys=ON;")
        return conn

    def _ensure_table(self, conn: sqlite3.Connection) -> None:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS domain_reputation (
                domain TEXT PRIMARY KEY,
                adjustment REAL NOT NULL DEFAULT 0.0,
                query_count INTEGER NOT NULL DEFAULT 0,
                correction_count INTEGER NOT NULL DEFAULT 0,
                updated_at TEXT NOT NULL
            );
            """
        )

    def get_adjustment(self, domain: str) -> float:
        domain = str(domain or "").strip().lower()
        if not domain:
            return 0.0
        try:
            with self._connect() as conn:
                self._ensure_table(conn)
                row = conn.execute(
                    "SELECT adjustment FROM domain_reputation WHERE domain = ?;", (domain,)
                ).fetchone()
                return float(row["adjustment"]) if row else 0.0
        except Exception:
            return 0.0

    def record_success(self, domain: str) -> None:
        """Source was used in a successful research result. Slowly recovers adjustment toward 0."""
        domain = str(domain or "").strip().lower()
        if not domain:
            return
        try:
            with self._connect() as conn:
                self._ensure_table(conn)
                conn.execute(
                    """
                    INSERT INTO domain_reputation (domain, adjustment, query_count, correction_count, updated_at)
                    VALUES (?, 0.0, 1, 0, ?)
                    ON CONFLICT(domain) DO UPDATE SET
                        adjustment = MIN(0.0, adjustment + 0.01),
                        query_count = query_count + 1,
                        updated_at = excluded.updated_at;
                    """,
                    (domain, _now_iso()),
                )
        except Exception:
            pass

    def record_correction(self, domain: str) -> None:
        """Source contributed to incorrect or flagged output. Penalizes future score."""
        domain = str(domain or "").strip().lower()
        if not domain:
            return
        try:
            with self._connect() as conn:
                self._ensure_table(conn)
                conn.execute(
                    """
                    INSERT INTO domain_reputation (domain, adjustment, query_count, correction_count, updated_at)
                    VALUES (?, -0.05, 0, 1, ?)
                    ON CONFLICT(domain) DO UPDATE SET
                        adjustment = MAX(-0.3, adjustment - 0.05),
                        correction_count = correction_count + 1,
                        updated_at = excluded.updated_at;
                    """,
                    (domain, _now_iso()),
                )
        except Exception:
            pass

    def get_all(self) -> list[dict[str, Any]]:
        try:
            with self._connect() as conn:
                self._ensure_table(conn)
                rows = conn.execute(
                    "SELECT domain, adjustment, query_count, correction_count, updated_at "
                    "FROM domain_reputation ORDER BY adjustment ASC, correction_count DESC;"
                ).fetchall()
                return [dict(r) for r in rows]
        except Exception:
            return []
