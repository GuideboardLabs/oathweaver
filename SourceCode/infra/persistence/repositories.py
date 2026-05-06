from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from shared_tools.db import row_to_dict, transaction
from shared_tools.topic_engine import VALID_TOPIC_TYPES
from .sqlite_db import connect_db, ensure_state_db


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _normalize_project_slug(raw: str | None) -> str:
    text = "_".join(str(raw or "").strip().split()).lower()
    return text or "general"


def _normalize_mode(raw: str | None) -> str:
    value = str(raw or "").strip().lower()
    aliases = {"research": "discovery", "extend": "discovery", "extend_oathweaver": "discovery", "foraging": "discovery", "plan": "discovery", "build": "make", "build_make": "make", "build/make": "make"}
    value = aliases.get(value, value)
    return value if value in {"discovery", "make"} else "discovery"


def _normalize_target(raw: str | None) -> str:
    value = str(raw or "").strip().lower()
    aliases = {"standalone_app": "app", "web_app": "app", "app": "app", "module": "app", "widget": "app", "standalone": "app", "script": "tool", "game_design_doc": "report", "gdd": "report", "document": "report", "memoir": "novel", "book": "novel", "book_draft": "novel", "email": "brief", "general": "auto", "gen": "auto", "medical": "auto", "med": "auto", "health": "auto", "animal_care": "auto", "pet_care": "auto", "veterinary": "auto", "finance": "auto", "financial": "auto", "fin": "auto", "sports": "auto", "sport": "auto", "history": "auto", "historical": "auto"}
    value = aliases.get(value, value)
    return value if value in {"auto", "essay", "brief", "app", "product", "gap_analysis", "novel", "report", "tool"} else "auto"


def _normalize_topic_type(raw: str | None) -> str:
    value = str(raw or "").strip().lower()
    return value if value in VALID_TOPIC_TYPES else "general_research"


class ProjectPipelineRepository:
    def __init__(self, repo_root: Path) -> None:
        self.repo_root = Path(repo_root)
        self.legacy_path = self.repo_root / "Runtime" / "project_pipeline.json"
        ensure_state_db(self.repo_root)
        self._migrate_legacy_json_if_needed()

    def _migrate_legacy_json_if_needed(self) -> None:
        if not self.legacy_path.exists():
            return
        with connect_db(self.repo_root) as conn:
            count = int(conn.execute("SELECT COUNT(*) FROM project_pipeline_states;").fetchone()[0])
            if count > 0:
                return
        try:
            payload = json.loads(self.legacy_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return
        projects = payload.get("projects", {}) if isinstance(payload, dict) else {}
        if not isinstance(projects, dict):
            return
        with connect_db(self.repo_root) as conn, transaction(conn, immediate=True):
            for key, value in projects.items():
                row = value if isinstance(value, dict) else {}
                slug = _normalize_project_slug(key)
                conn.execute(
                    """
                    INSERT INTO project_pipeline_states(project_slug, mode, target, topic_type, updated_at)
                    VALUES (?, ?, ?, ?, ?)
                    ON CONFLICT(project_slug) DO UPDATE SET
                        mode = excluded.mode,
                        target = excluded.target,
                        topic_type = excluded.topic_type,
                        updated_at = excluded.updated_at;
                    """.strip(),
                    (slug, _normalize_mode(row.get("mode")), _normalize_target(row.get("target")), _normalize_topic_type(row.get("topic_type")), str(row.get("updated_at", "")).strip() or _now_iso()),
                )

    def get(self, project: str | None) -> dict[str, Any]:
        slug = _normalize_project_slug(project)
        with connect_db(self.repo_root) as conn:
            row = row_to_dict(conn.execute("SELECT * FROM project_pipeline_states WHERE project_slug = ?;", (slug,)).fetchone()) or {}
        return {"project": slug, "mode": _normalize_mode(row.get("mode")), "target": _normalize_target(row.get("target")), "topic_type": _normalize_topic_type(row.get("topic_type")), "updated_at": str(row.get("updated_at", "")).strip()}

    def set(self, project: str | None, *, mode: str | None = None, target: str | None = None, topic_type: str | None = None) -> dict[str, Any]:
        current = self.get(project)
        slug = current["project"]
        next_mode = _normalize_mode(mode) if mode is not None else _normalize_mode(current.get("mode"))
        next_target = _normalize_target(target) if target is not None else _normalize_target(current.get("target"))
        next_topic_type = _normalize_topic_type(topic_type) if topic_type is not None else _normalize_topic_type(current.get("topic_type"))
        updated_at = _now_iso()
        with connect_db(self.repo_root) as conn, transaction(conn, immediate=True):
            conn.execute(
                """
                INSERT INTO project_pipeline_states(project_slug, mode, target, topic_type, updated_at)
                VALUES (?, ?, ?, ?, ?)
                ON CONFLICT(project_slug) DO UPDATE SET
                    mode = excluded.mode,
                    target = excluded.target,
                    topic_type = excluded.topic_type,
                    updated_at = excluded.updated_at;
                """.strip(),
                (slug, next_mode, next_target, next_topic_type, updated_at),
            )
        return {"project": slug, "mode": next_mode, "target": next_target, "topic_type": next_topic_type, "updated_at": updated_at}

    def list_all(self) -> dict[str, dict[str, Any]]:
        with connect_db(self.repo_root) as conn:
            rows = conn.execute("SELECT * FROM project_pipeline_states ORDER BY project_slug ASC;").fetchall()
        out = {}
        for row in rows:
            item = row_to_dict(row) or {}
            slug = _normalize_project_slug(item.get("project_slug"))
            out[slug] = {"project": slug, "mode": _normalize_mode(item.get("mode")), "target": _normalize_target(item.get("target")), "topic_type": _normalize_topic_type(item.get("topic_type")), "updated_at": str(item.get("updated_at", "")).strip()}
        return out

    def clear_all(self) -> None:
        with connect_db(self.repo_root) as conn, transaction(conn, immediate=True):
            conn.execute("DELETE FROM project_pipeline_states;")


class WatchtowerRepository:
    def __init__(self, repo_root: Path) -> None:
        self.repo_root = Path(repo_root)
        self.legacy_watches_path = self.repo_root / "Runtime" / "watchtower" / "watches.json"
        self.legacy_briefings_path = self.repo_root / "Runtime" / "watchtower" / "briefing_state.json"
        ensure_state_db(self.repo_root)
        self._migrate_legacy_json_if_needed()

    def _migrate_legacy_json_if_needed(self) -> None:
        with connect_db(self.repo_root) as conn:
            counts = (
                int(conn.execute("SELECT COUNT(*) FROM watchtower_watches;").fetchone()[0]),
                int(conn.execute("SELECT COUNT(*) FROM watchtower_briefings;").fetchone()[0]),
            )
        if counts == (0, 0):
            self._migrate_watches()
            self._migrate_briefings()

    def _migrate_watches(self) -> None:
        if not self.legacy_watches_path.exists():
            return
        try:
            rows = json.loads(self.legacy_watches_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return
        if not isinstance(rows, list):
            return
        with connect_db(self.repo_root) as conn, transaction(conn, immediate=True):
            for row in rows:
                if not isinstance(row, dict):
                    continue
                conn.execute(
                    """
                    INSERT INTO watchtower_watches(id, topic, profile, schedule, schedule_hour, enabled, last_run_at, created_at, updated_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                    ON CONFLICT(id) DO NOTHING;
                    """.strip(),
                    (
                        str(row.get("id", "")).strip(),
                        str(row.get("topic", "")).strip(),
                        str(row.get("profile", "general")).strip(),
                        str(row.get("schedule", "daily")).strip(),
                        int(row.get("schedule_hour", 7) or 7),
                        1 if bool(row.get("enabled", True)) else 0,
                        str(row.get("last_run_at", "")).strip(),
                        str(row.get("created_at", "")).strip() or _now_iso(),
                        str(row.get("updated_at", "")).strip(),
                    ),
                )

    def _migrate_briefings(self) -> None:
        if not self.legacy_briefings_path.exists():
            return
        try:
            payload = json.loads(self.legacy_briefings_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return
        if not isinstance(payload, dict):
            return
        with connect_db(self.repo_root) as conn, transaction(conn, immediate=True):
            for key, row in payload.items():
                if not isinstance(row, dict):
                    continue
                conn.execute(
                    """
                    INSERT INTO watchtower_briefings(id, watch_id, topic, path, preview, created_at, is_read)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                    ON CONFLICT(id) DO NOTHING;
                    """.strip(),
                    (
                        str(row.get("id", key)).strip() or str(key),
                        str(row.get("watch_id", "")).strip(),
                        str(row.get("topic", "")).strip(),
                        str(row.get("path", "")).strip(),
                        str(row.get("preview", "")).strip(),
                        str(row.get("created_at", "")).strip() or _now_iso(),
                        1 if bool(row.get("read", False)) else 0,
                    ),
                )

    def list_watches(self) -> list[dict[str, Any]]:
        with connect_db(self.repo_root) as conn:
            rows = conn.execute("SELECT * FROM watchtower_watches ORDER BY created_at ASC, id ASC;").fetchall()
        out = []
        for row in rows:
            item = row_to_dict(row) or {}
            item["enabled"] = bool(int(item.get("enabled", 0) or 0))
            out.append(item)
        return out

    def add_watch(self, watch: dict[str, Any]) -> dict[str, Any]:
        with connect_db(self.repo_root) as conn, transaction(conn, immediate=True):
            conn.execute(
                "INSERT INTO watchtower_watches(id, topic, profile, schedule, schedule_hour, enabled, last_run_at, created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?);",
                (watch["id"], watch["topic"], watch["profile"], watch["schedule"], int(watch["schedule_hour"]), 1 if watch.get("enabled", True) else 0, watch.get("last_run_at", ""), watch.get("created_at", _now_iso()), watch.get("updated_at", "")),
            )
        return self.get_watch(watch["id"]) or dict(watch)

    def get_watch(self, watch_id: str) -> dict[str, Any] | None:
        with connect_db(self.repo_root) as conn:
            row = row_to_dict(conn.execute("SELECT * FROM watchtower_watches WHERE id = ?;", (watch_id,)).fetchone())
        if row is None:
            return None
        row["enabled"] = bool(int(row.get("enabled", 0) or 0))
        return row

    def update_watch(self, watch_id: str, **fields: Any) -> dict[str, Any] | None:
        current = self.get_watch(watch_id)
        if current is None:
            return None
        allowed = {"topic", "profile", "schedule", "schedule_hour", "enabled", "last_run_at"}
        for key, value in fields.items():
            if key not in allowed:
                continue
            current[key] = value
        current["updated_at"] = _now_iso()
        with connect_db(self.repo_root) as conn, transaction(conn, immediate=True):
            conn.execute(
                """
                UPDATE watchtower_watches
                SET topic = ?, profile = ?, schedule = ?, schedule_hour = ?, enabled = ?, last_run_at = ?, updated_at = ?
                WHERE id = ?;
                """.strip(),
                (current.get("topic", ""), current.get("profile", "general"), current.get("schedule", "daily"), int(current.get("schedule_hour", 7) or 7), 1 if bool(current.get("enabled", True)) else 0, current.get("last_run_at", ""), current["updated_at"], watch_id),
            )
        return self.get_watch(watch_id)

    def delete_watch(self, watch_id: str) -> bool:
        with connect_db(self.repo_root) as conn, transaction(conn, immediate=True):
            cur = conn.execute("DELETE FROM watchtower_watches WHERE id = ?;", (watch_id,))
        return int(cur.rowcount or 0) > 0

    def save_briefing(self, entry: dict[str, Any]) -> None:
        with connect_db(self.repo_root) as conn, transaction(conn, immediate=True):
            conn.execute(
                """
                INSERT INTO watchtower_briefings(id, watch_id, topic, path, preview, created_at, is_read)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(id) DO UPDATE SET
                    watch_id = excluded.watch_id,
                    topic = excluded.topic,
                    path = excluded.path,
                    preview = excluded.preview,
                    created_at = excluded.created_at,
                    is_read = excluded.is_read;
                """.strip(),
                (entry["id"], entry.get("watch_id", ""), entry.get("topic", ""), entry.get("path", ""), entry.get("preview", ""), entry.get("created_at", _now_iso()), 1 if bool(entry.get("read", False)) else 0),
            )

    def list_briefings(self, limit: int = 50) -> list[dict[str, Any]]:
        limit = max(1, min(500, int(limit or 50)))
        with connect_db(self.repo_root) as conn:
            rows = conn.execute("SELECT * FROM watchtower_briefings ORDER BY created_at DESC, id DESC LIMIT ?;", (limit,)).fetchall()
        out = []
        for row in rows:
            item = row_to_dict(row) or {}
            item["read"] = bool(int(item.pop("is_read", 0) or 0))
            out.append(item)
        return out

    def get_briefing(self, briefing_id: str) -> dict[str, Any] | None:
        with connect_db(self.repo_root) as conn:
            row = conn.execute("SELECT * FROM watchtower_briefings WHERE id = ?;", (briefing_id,)).fetchone()
        item = row_to_dict(row) if row is not None else None
        if not item:
            return None
        item["read"] = bool(int(item.pop("is_read", 0) or 0))
        return item

    def mark_read(self, briefing_id: str) -> bool:
        with connect_db(self.repo_root) as conn, transaction(conn, immediate=True):
            cur = conn.execute("UPDATE watchtower_briefings SET is_read = 1 WHERE id = ?;", (briefing_id,))
        return int(cur.rowcount or 0) > 0

    def mark_unread(self, briefing_id: str) -> bool:
        with connect_db(self.repo_root) as conn, transaction(conn, immediate=True):
            cur = conn.execute("UPDATE watchtower_briefings SET is_read = 0 WHERE id = ?;", (briefing_id,))
        return int(cur.rowcount or 0) > 0

    def unread_count(self) -> int:
        with connect_db(self.repo_root) as conn:
            return int(conn.execute("SELECT COUNT(*) FROM watchtower_briefings WHERE is_read = 0;").fetchone()[0])

    def clear_all(self) -> None:
        with connect_db(self.repo_root) as conn, transaction(conn, immediate=True):
            conn.execute("DELETE FROM watchtower_briefings;")
            conn.execute("DELETE FROM watchtower_watches;")


class ForageCardRepository:
    def __init__(self, repo_root: Path) -> None:
        self.repo_root = Path(repo_root)
        ensure_state_db(self.repo_root)

    def save_card(self, entry: dict[str, Any]) -> None:
        now = _now_iso()
        with connect_db(self.repo_root) as conn, transaction(conn, immediate=True):
            conn.execute(
                """
                INSERT INTO forage_cards(id, title, project, summary_path, raw_path, query, preview,
                    source_count, is_pinned, is_read, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(id) DO UPDATE SET
                    title = excluded.title,
                    project = excluded.project,
                    summary_path = excluded.summary_path,
                    raw_path = excluded.raw_path,
                    query = excluded.query,
                    preview = excluded.preview,
                    source_count = excluded.source_count,
                    updated_at = excluded.updated_at;
                """.strip(),
                (
                    str(entry["id"]),
                    str(entry.get("title", "")),
                    str(entry.get("project", "")),
                    str(entry.get("summary_path", "")),
                    str(entry.get("raw_path", "")),
                    str(entry.get("query", "")),
                    str(entry.get("preview", "")),
                    int(entry.get("source_count", 0) or 0),
                    int(entry.get("is_pinned", 0) or 0),
                    int(entry.get("is_read", 0) or 0),
                    str(entry.get("created_at", now)),
                    now,
                ),
            )

    def list_cards(self, limit: int = 50) -> list[dict[str, Any]]:
        limit = max(1, min(500, int(limit or 50)))
        with connect_db(self.repo_root) as conn:
            rows = conn.execute(
                "SELECT * FROM forage_cards ORDER BY is_pinned DESC, created_at DESC LIMIT ?;",
                (limit,),
            ).fetchall()
        return [row_to_dict(r) or {} for r in rows]

    def get_card(self, card_id: str) -> dict[str, Any] | None:
        with connect_db(self.repo_root) as conn:
            row = conn.execute("SELECT * FROM forage_cards WHERE id = ?;", (card_id,)).fetchone()
        return row_to_dict(row) if row is not None else None

    def resolve_card_id(self, card_id_or_request_id: str) -> str:
        raw = str(card_id_or_request_id or "").strip()
        if not raw:
            return ""
        # Primary path: caller already passed a forage card id.
        if self.get_card(raw) is not None:
            return raw
        # Compatibility path: chat quick-actions pass request_id while card ids are fc_<request[:12]>_<suffix>.
        req_prefix = raw[:12].strip()
        if not req_prefix:
            return ""
        like_pattern = f"fc_{req_prefix}_%"
        with connect_db(self.repo_root) as conn:
            row = conn.execute(
                "SELECT id FROM forage_cards WHERE id LIKE ? ORDER BY created_at DESC LIMIT 1;",
                (like_pattern,),
            ).fetchone()
        if row is None:
            return ""
        payload = row_to_dict(row) or {}
        return str(payload.get("id", "")).strip()

    def pin_card(self, card_id: str) -> bool:
        with connect_db(self.repo_root) as conn, transaction(conn, immediate=True):
            cur = conn.execute(
                "UPDATE forage_cards SET is_pinned = 1, updated_at = ? WHERE id = ?;",
                (_now_iso(), card_id),
            )
        return int(cur.rowcount or 0) > 0

    def unpin_card(self, card_id: str) -> bool:
        with connect_db(self.repo_root) as conn, transaction(conn, immediate=True):
            cur = conn.execute(
                "UPDATE forage_cards SET is_pinned = 0, updated_at = ? WHERE id = ?;",
                (_now_iso(), card_id),
            )
        return int(cur.rowcount or 0) > 0

    def delete_card(self, card_id: str) -> bool:
        with connect_db(self.repo_root) as conn, transaction(conn, immediate=True):
            cur = conn.execute("DELETE FROM forage_cards WHERE id = ?;", (card_id,))
        return int(cur.rowcount or 0) > 0

    def pinned_count(self) -> int:
        with connect_db(self.repo_root) as conn:
            return int(conn.execute("SELECT COUNT(*) FROM forage_cards WHERE is_pinned = 1;").fetchone()[0])

    def total_count(self) -> int:
        with connect_db(self.repo_root) as conn:
            return int(conn.execute("SELECT COUNT(*) FROM forage_cards;").fetchone()[0])


__all__ = ["ProjectPipelineRepository", "WatchtowerRepository", "ForageCardRepository"]
