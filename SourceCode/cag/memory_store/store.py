from __future__ import annotations

import json
import sqlite3
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .schema import MemoryRow, build_memory_row


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


class CAGMemoryStore:
    """Hybrid CAG memory store: append-only JSONL events + mutable SQLite rows."""

    def __init__(self, repo_root: Path) -> None:
        self.repo_root = Path(repo_root)
        self.root = self.repo_root / "Runtime" / "cag"
        self.root.mkdir(parents=True, exist_ok=True)
        self.rows_path = self.root / "memory_rows.jsonl"
        self.db_path = self.root / "memory_rows.sqlite3"
        if not self.rows_path.exists():
            self.rows_path.write_text("", encoding="utf-8")
        self._ensure_db()

    def add_row(self, payload: dict[str, Any]) -> dict[str, Any]:
        memory_id = str(payload.get("memory_id", "")).strip() or self._new_memory_id()
        now = _now_iso()
        row = build_memory_row(payload, memory_id=memory_id, now_iso=now)
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                """
                INSERT INTO memory_rows(
                    memory_id, text, scope, scope_level, domain, topic, thread, project, run,
                    type, status, evidence_json, supersedes_json, superseded_by_json, confidence,
                    human_status, tags_json, promoted_terms_json, source, created_at, updated_at,
                    expires_at, validation_json, contradictions_json
                ) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
                """,
                (
                    row.memory_id,
                    row.text,
                    row.scope,
                    row.scope_level,
                    row.domain,
                    row.topic,
                    row.thread,
                    row.project,
                    row.run,
                    row.type,
                    row.status,
                    json.dumps(row.evidence, ensure_ascii=True),
                    json.dumps(row.supersedes, ensure_ascii=True),
                    json.dumps(row.superseded_by, ensure_ascii=True),
                    float(row.confidence),
                    row.human_status,
                    json.dumps(row.tags, ensure_ascii=True),
                    json.dumps(row.promoted_terms, ensure_ascii=True),
                    row.source,
                    row.created_at,
                    row.updated_at,
                    row.expires_at,
                    json.dumps(row.validation, ensure_ascii=True),
                    json.dumps(row.contradictions, ensure_ascii=True),
                ),
            )
            conn.commit()
        self._append_event({"event": "upsert", "row": row.as_dict(), "created_at": now})
        return row.as_dict()

    def update_row(self, memory_id: str, patch: dict[str, Any]) -> dict[str, Any] | None:
        current = self.get_row(memory_id)
        if not current:
            return None
        merged = dict(current)
        for key, value in dict(patch or {}).items():
            merged[key] = value
        merged["memory_id"] = str(memory_id)
        merged["updated_at"] = _now_iso()
        row = build_memory_row(merged, memory_id=str(memory_id), now_iso=str(merged["updated_at"]))
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                """
                UPDATE memory_rows
                SET text=?, scope=?, scope_level=?, domain=?, topic=?, thread=?, project=?, run=?,
                    type=?, status=?, evidence_json=?, supersedes_json=?, superseded_by_json=?, confidence=?,
                    human_status=?, tags_json=?, promoted_terms_json=?, source=?, updated_at=?,
                    expires_at=?, validation_json=?, contradictions_json=?
                WHERE memory_id=?
                """,
                (
                    row.text,
                    row.scope,
                    row.scope_level,
                    row.domain,
                    row.topic,
                    row.thread,
                    row.project,
                    row.run,
                    row.type,
                    row.status,
                    json.dumps(row.evidence, ensure_ascii=True),
                    json.dumps(row.supersedes, ensure_ascii=True),
                    json.dumps(row.superseded_by, ensure_ascii=True),
                    float(row.confidence),
                    row.human_status,
                    json.dumps(row.tags, ensure_ascii=True),
                    json.dumps(row.promoted_terms, ensure_ascii=True),
                    row.source,
                    row.updated_at,
                    row.expires_at,
                    json.dumps(row.validation, ensure_ascii=True),
                    json.dumps(row.contradictions, ensure_ascii=True),
                    row.memory_id,
                ),
            )
            conn.commit()
        self._append_event({"event": "update", "memory_id": row.memory_id, "patch": dict(patch or {}), "created_at": row.updated_at})
        return row.as_dict()

    def get_row(self, memory_id: str) -> dict[str, Any] | None:
        key = str(memory_id or "").strip()
        if not key:
            return None
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            row = conn.execute("SELECT * FROM memory_rows WHERE memory_id=?", (key,)).fetchone()
        if row is None:
            return None
        return self._row_to_dict(row)

    def list_rows(
        self,
        *,
        project: str = "",
        statuses: list[str] | None = None,
        scope_levels: list[str] | None = None,
        memory_types: list[str] | None = None,
        include_expired: bool = False,
        include_superseded: bool = False,
        limit: int = 200,
    ) -> list[dict[str, Any]]:
        where: list[str] = []
        args: list[Any] = []
        if project:
            where.append("project=?")
            args.append(str(project).strip())
        if statuses:
            valid = [str(x).strip().lower() for x in statuses if str(x).strip()]
            if valid:
                where.append("status IN (" + ",".join(["?"] * len(valid)) + ")")
                args.extend(valid)
        if scope_levels:
            valid_levels = [str(x).strip().lower() for x in scope_levels if str(x).strip()]
            if valid_levels:
                where.append("scope_level IN (" + ",".join(["?"] * len(valid_levels)) + ")")
                args.extend(valid_levels)
        if memory_types:
            valid_types = [str(x).strip().lower() for x in memory_types if str(x).strip()]
            if valid_types:
                where.append("type IN (" + ",".join(["?"] * len(valid_types)) + ")")
                args.extend(valid_types)
        if not include_expired:
            where.append("status != 'expired'")
        if not include_superseded:
            where.append("status != 'superseded'")

        sql = "SELECT * FROM memory_rows"
        if where:
            sql += " WHERE " + " AND ".join(where)
        sql += " ORDER BY updated_at DESC LIMIT ?"
        args.append(max(1, int(limit)))

        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            rows = conn.execute(sql, tuple(args)).fetchall()
        return [self._row_to_dict(row) for row in rows]

    def list_rows_for_projects(
        self,
        *,
        projects: list[str],
        statuses: list[str] | None = None,
        scope_levels: list[str] | None = None,
        memory_types: list[str] | None = None,
        include_expired: bool = False,
        include_superseded: bool = False,
        limit: int = 500,
    ) -> list[dict[str, Any]]:
        """Batch variant of list_rows() that resolves multiple projects in one query."""
        normalized_projects = [str(p).strip() for p in projects if str(p).strip()]
        if not normalized_projects:
            return self.list_rows(
                statuses=statuses,
                scope_levels=scope_levels,
                memory_types=memory_types,
                include_expired=include_expired,
                include_superseded=include_superseded,
                limit=limit,
            )

        where: list[str] = ["project IN (" + ",".join(["?"] * len(normalized_projects)) + ")"]
        args: list[Any] = list(normalized_projects)
        if statuses:
            valid = [str(x).strip().lower() for x in statuses if str(x).strip()]
            if valid:
                where.append("status IN (" + ",".join(["?"] * len(valid)) + ")")
                args.extend(valid)
        if scope_levels:
            valid_levels = [str(x).strip().lower() for x in scope_levels if str(x).strip()]
            if valid_levels:
                where.append("scope_level IN (" + ",".join(["?"] * len(valid_levels)) + ")")
                args.extend(valid_levels)
        if memory_types:
            valid_types = [str(x).strip().lower() for x in memory_types if str(x).strip()]
            if valid_types:
                where.append("type IN (" + ",".join(["?"] * len(valid_types)) + ")")
                args.extend(valid_types)
        if not include_expired:
            where.append("status != 'expired'")
        if not include_superseded:
            where.append("status != 'superseded'")

        sql = "SELECT * FROM memory_rows WHERE " + " AND ".join(where) + " ORDER BY updated_at DESC LIMIT ?"
        args.append(max(1, int(limit)))
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            rows = conn.execute(sql, tuple(args)).fetchall()
        return [self._row_to_dict(row) for row in rows]

    def mark_supersession(self, *, old_memory_id: str, new_memory_id: str) -> None:
        old_row = self.get_row(old_memory_id)
        new_row = self.get_row(new_memory_id)
        if not old_row or not new_row:
            return
        superseded_by = list(old_row.get("superseded_by", []))
        if new_memory_id not in superseded_by:
            superseded_by.append(new_memory_id)
        self.update_row(old_memory_id, {"status": "superseded", "superseded_by": superseded_by})

        supersedes = list(new_row.get("supersedes", []))
        if old_memory_id not in supersedes:
            supersedes.append(old_memory_id)
        self.update_row(new_memory_id, {"supersedes": supersedes})

    def _new_memory_id(self) -> str:
        stamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        return f"mem_{stamp}_{uuid.uuid4().hex[:8]}"

    def _append_event(self, payload: dict[str, Any]) -> None:
        with self.rows_path.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(payload, ensure_ascii=True))
            fh.write("\n")

    def _ensure_db(self) -> None:
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS memory_rows(
                    memory_id TEXT PRIMARY KEY,
                    text TEXT NOT NULL,
                    scope TEXT,
                    scope_level TEXT,
                    domain TEXT,
                    topic TEXT,
                    thread TEXT,
                    project TEXT,
                    run TEXT,
                    type TEXT,
                    status TEXT,
                    evidence_json TEXT,
                    supersedes_json TEXT,
                    superseded_by_json TEXT,
                    confidence REAL,
                    human_status TEXT,
                    tags_json TEXT,
                    promoted_terms_json TEXT,
                    source TEXT,
                    created_at TEXT,
                    updated_at TEXT,
                    expires_at TEXT,
                    validation_json TEXT,
                    contradictions_json TEXT
                )
                """
            )
            conn.execute("CREATE INDEX IF NOT EXISTS idx_memory_rows_project ON memory_rows(project)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_memory_rows_scope_level ON memory_rows(scope_level)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_memory_rows_status ON memory_rows(status)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_memory_rows_type ON memory_rows(type)")
            conn.commit()

    @staticmethod
    def _loads_json(value: Any, default: Any) -> Any:
        if value is None:
            return default
        text = str(value)
        if not text.strip():
            return default
        try:
            parsed = json.loads(text)
            return parsed
        except Exception:
            return default

    def _row_to_dict(self, row: sqlite3.Row) -> dict[str, Any]:
        data = dict(row)
        out = {
            "memory_id": str(data.get("memory_id", "")),
            "text": str(data.get("text", "")),
            "scope": str(data.get("scope", "")),
            "scope_level": str(data.get("scope_level", "")),
            "domain": str(data.get("domain", "")),
            "topic": str(data.get("topic", "")),
            "thread": str(data.get("thread", "")),
            "project": str(data.get("project", "")),
            "run": str(data.get("run", "")),
            "type": str(data.get("type", "decision")),
            "memory_type": str(data.get("type", "decision")),
            "status": str(data.get("status", "candidate")),
            "evidence": self._loads_json(data.get("evidence_json"), []),
            "supersedes": self._loads_json(data.get("supersedes_json"), []),
            "superseded_by": self._loads_json(data.get("superseded_by_json"), []),
            "confidence": float(data.get("confidence", 0.0) or 0.0),
            "human_status": str(data.get("human_status", "unreviewed")),
            "tags": self._loads_json(data.get("tags_json"), []),
            "promoted_terms": self._loads_json(data.get("promoted_terms_json"), []),
            "source": str(data.get("source", "promotion_gate")),
            "created_at": str(data.get("created_at", "")),
            "updated_at": str(data.get("updated_at", "")),
            "expires_at": str(data.get("expires_at", "")),
            "validation": self._loads_json(data.get("validation_json"), {}),
            "contradictions": self._loads_json(data.get("contradictions_json"), []),
        }
        return out
