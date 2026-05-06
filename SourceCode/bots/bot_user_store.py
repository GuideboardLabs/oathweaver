from __future__ import annotations

import secrets
from datetime import datetime, timezone
from pathlib import Path
from threading import Lock
from typing import Any

from shared_tools.db import connect, row_to_dict, transaction


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


class BotUserStore:
    def __init__(self, repo_root: Path) -> None:
        self.repo_root = repo_root
        self.lock = Lock()

    def get_mapping(self, platform: str, platform_user_id: str) -> dict[str, Any] | None:
        with self.lock, connect(self.repo_root) as conn:
            row = conn.execute(
                "SELECT * FROM bot_user_mappings WHERE platform = ? AND platform_user_id = ?;",
                (platform, str(platform_user_id)),
            ).fetchone()
            return row_to_dict(row)

    def create_mapping(
        self,
        platform: str,
        platform_user_id: str,
        platform_username: str,
        oathweaver_user_id: str,
        conversation_id: str,
    ) -> dict[str, Any]:
        now = _now_iso()
        row_id = f"bm_{secrets.token_hex(6)}"
        with self.lock, connect(self.repo_root) as conn:
            with transaction(conn, immediate=True):
                conn.execute(
                    """
                    INSERT INTO bot_user_mappings(
                        id, platform, platform_user_id, platform_username,
                        oathweaver_user_id, conversation_id, created_at, updated_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    ON CONFLICT(platform, platform_user_id) DO UPDATE SET
                        platform_username = excluded.platform_username,
                        oathweaver_user_id = excluded.oathweaver_user_id,
                        conversation_id = excluded.conversation_id,
                        updated_at = excluded.updated_at;
                    """.strip(),
                    (row_id, platform, str(platform_user_id), platform_username,
                     oathweaver_user_id, conversation_id, now, now),
                )
            row = conn.execute(
                "SELECT * FROM bot_user_mappings WHERE platform = ? AND platform_user_id = ?;",
                (platform, str(platform_user_id)),
            ).fetchone()
            return row_to_dict(row) or {}

    def update_conversation(self, platform: str, platform_user_id: str, conversation_id: str) -> None:
        with self.lock, connect(self.repo_root) as conn:
            with transaction(conn, immediate=True):
                conn.execute(
                    "UPDATE bot_user_mappings SET conversation_id = ?, updated_at = ? "
                    "WHERE platform = ? AND platform_user_id = ?;",
                    (conversation_id, _now_iso(), platform, str(platform_user_id)),
                )

    def list_mappings(self, platform: str | None = None) -> list[dict[str, Any]]:
        with self.lock, connect(self.repo_root) as conn:
            if platform:
                rows = conn.execute(
                    "SELECT * FROM bot_user_mappings WHERE platform = ? ORDER BY created_at DESC;",
                    (platform,),
                ).fetchall()
            else:
                rows = conn.execute(
                    "SELECT * FROM bot_user_mappings ORDER BY platform, created_at DESC;"
                ).fetchall()
            return [row_to_dict(r) for r in rows if row_to_dict(r) is not None]

    def delete_mapping(self, mapping_id: str) -> bool:
        with self.lock, connect(self.repo_root) as conn:
            with transaction(conn, immediate=True):
                cursor = conn.execute(
                    "DELETE FROM bot_user_mappings WHERE id = ?;", (mapping_id,)
                )
            return cursor.rowcount > 0
