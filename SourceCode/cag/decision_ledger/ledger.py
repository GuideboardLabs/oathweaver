from __future__ import annotations

import json
import sqlite3
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


DECISION_TYPES: tuple[str, ...] = ("decision", "constraint", "lesson", "benchmark_implication")


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


class DecisionLedger:
    """Queryable ledger for architecture/project decisions derived from CAG memory."""

    def __init__(self, repo_root: Path) -> None:
        self.repo_root = Path(repo_root)
        self.root = self.repo_root / "Runtime" / "cag"
        self.root.mkdir(parents=True, exist_ok=True)
        self.events_path = self.root / "decision_ledger.jsonl"
        self.db_path = self.root / "decision_ledger.sqlite3"
        if not self.events_path.exists():
            self.events_path.write_text("", encoding="utf-8")
        self._ensure_db()

    def add_entry(
        self,
        *,
        memory_row: dict[str, Any],
        rationale: str = "",
        status: str = "accepted",
    ) -> dict[str, Any] | None:
        row_type = str(memory_row.get("type", memory_row.get("memory_type", ""))).strip().lower()
        if row_type not in DECISION_TYPES:
            return None
        decision_id = f"DL-{uuid.uuid4().hex[:10].upper()}"
        now = _now_iso()
        payload = {
            "decision_id": decision_id,
            "memory_id": str(memory_row.get("memory_id", "")).strip(),
            "project": str(memory_row.get("project", "")).strip(),
            "domain": str(memory_row.get("domain", "")).strip(),
            "topic": str(memory_row.get("topic", "")).strip(),
            "thread": str(memory_row.get("thread", "")).strip(),
            "scope": str(memory_row.get("scope", "")).strip(),
            "scope_level": str(memory_row.get("scope_level", "")).strip(),
            "decision_type": row_type,
            "decision_text": str(memory_row.get("text", "")).strip(),
            "rationale": str(rationale or "").strip(),
            "status": str(status or "accepted").strip().lower(),
            "evidence": [dict(x) for x in memory_row.get("evidence", []) if isinstance(x, dict)],
            "created_at": now,
            "updated_at": now,
        }
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                """
                INSERT INTO decision_ledger(
                    decision_id, memory_id, project, domain, topic, thread, scope, scope_level,
                    decision_type, decision_text, rationale, status, evidence_json, created_at, updated_at
                ) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
                """,
                (
                    payload["decision_id"],
                    payload["memory_id"],
                    payload["project"],
                    payload["domain"],
                    payload["topic"],
                    payload["thread"],
                    payload["scope"],
                    payload["scope_level"],
                    payload["decision_type"],
                    payload["decision_text"],
                    payload["rationale"],
                    payload["status"],
                    json.dumps(payload["evidence"], ensure_ascii=True),
                    payload["created_at"],
                    payload["updated_at"],
                ),
            )
            conn.commit()

        self._append_event({"event": "decision_added", "payload": payload})
        return payload

    def list_entries(
        self,
        *,
        project: str = "",
        thread: str = "",
        limit: int = 100,
    ) -> list[dict[str, Any]]:
        where: list[str] = []
        args: list[Any] = []
        if project:
            where.append("project=?")
            args.append(str(project).strip())
        if thread:
            where.append("thread=?")
            args.append(str(thread).strip())

        sql = "SELECT * FROM decision_ledger"
        if where:
            sql += " WHERE " + " AND ".join(where)
        sql += " ORDER BY updated_at DESC LIMIT ?"
        args.append(max(1, int(limit)))

        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            rows = conn.execute(sql, tuple(args)).fetchall()
        return [self._row_to_dict(row) for row in rows]

    def _ensure_db(self) -> None:
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS decision_ledger(
                    decision_id TEXT PRIMARY KEY,
                    memory_id TEXT,
                    project TEXT,
                    domain TEXT,
                    topic TEXT,
                    thread TEXT,
                    scope TEXT,
                    scope_level TEXT,
                    decision_type TEXT,
                    decision_text TEXT,
                    rationale TEXT,
                    status TEXT,
                    evidence_json TEXT,
                    created_at TEXT,
                    updated_at TEXT
                )
                """
            )
            conn.execute("CREATE INDEX IF NOT EXISTS idx_decision_project ON decision_ledger(project)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_decision_thread ON decision_ledger(thread)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_decision_memory ON decision_ledger(memory_id)")
            conn.commit()

    def _append_event(self, payload: dict[str, Any]) -> None:
        with self.events_path.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(payload, ensure_ascii=True))
            fh.write("\n")

    @staticmethod
    def _row_to_dict(row: sqlite3.Row) -> dict[str, Any]:
        data = dict(row)
        evidence = []
        try:
            parsed = json.loads(str(data.get("evidence_json", "[]")))
            if isinstance(parsed, list):
                evidence = [dict(x) for x in parsed if isinstance(x, dict)]
        except Exception:
            evidence = []
        return {
            "decision_id": str(data.get("decision_id", "")),
            "memory_id": str(data.get("memory_id", "")),
            "project": str(data.get("project", "")),
            "domain": str(data.get("domain", "")),
            "topic": str(data.get("topic", "")),
            "thread": str(data.get("thread", "")),
            "scope": str(data.get("scope", "")),
            "scope_level": str(data.get("scope_level", "")),
            "decision_type": str(data.get("decision_type", "")),
            "decision_text": str(data.get("decision_text", "")),
            "rationale": str(data.get("rationale", "")),
            "status": str(data.get("status", "")),
            "evidence": evidence,
            "created_at": str(data.get("created_at", "")),
            "updated_at": str(data.get("updated_at", "")),
        }
