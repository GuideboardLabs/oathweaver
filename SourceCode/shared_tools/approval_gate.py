from __future__ import annotations

import json
import os
import sqlite3
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from shared_tools.db import connect, row_to_dict, transaction
from shared_tools.migrations import initialize_database


class ApprovalGate:
    def __init__(self, repo_root: Path) -> None:
        self.repo_root = Path(repo_root)
        initialize_database(self.repo_root)
        self.enabled = str(os.getenv("OATHWEAVER_APPROVAL_GATE", "1")).strip().lower() in {"1", "true", "yes", "on"}
        self.action_keywords = {
            "send",
            "email",
            "text",
            "book",
            "schedule",
            "cancel",
            "buy",
            "purchase",
            "pay",
            "delete",
            "submit",
        }

    def requires_approval(self, text: str, lane: str) -> bool:
        if not self.enabled:
            return False
        lower = text.lower()
        has_action = any(word in lower for word in self.action_keywords)
        lane_key = str(lane or "").strip().lower()
        return has_action and lane_key in {"project", "research", "action"}

    def create_request(self, lane: str, text: str, project_slug: str) -> str:
        request_id = uuid.uuid4().hex[:10]
        now = _now_iso()
        with connect(self.repo_root) as conn, transaction(conn, immediate=True):
            conn.execute(
                """
                INSERT INTO approvals (
                    id, record_type, lane, project, title, text,
                    action_type, action_payload_json, source, status,
                    created_at, decided_at, decision_reason
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
                """.strip(),
                (
                    request_id,
                    "approval_request",
                    lane,
                    _normalize_project(project_slug),
                    "",
                    text,
                    None,
                    None,
                    "approval_gate",
                    "pending",
                    now,
                    None,
                    None,
                ),
            )
        return request_id

    def list_pending(self) -> list[dict[str, Any]]:
        with connect(self.repo_root) as conn:
            rows = conn.execute(
                """
                SELECT id, record_type, lane, project, title, text,
                       action_type, action_payload_json, source, status,
                       created_at, decided_at, decision_reason
                FROM approvals
                WHERE status = 'pending'
                ORDER BY datetime(created_at) DESC, id DESC;
                """.strip()
            ).fetchall()
        return [_deserialize_row(row) for row in rows]

    def get_request(self, request_id: str) -> dict[str, Any] | None:
        """Return the stored approval_request row for *request_id*, or None if not found."""
        with connect(self.repo_root) as conn:
            row = conn.execute(
                """
                SELECT id, record_type, lane, project, title, text, status
                FROM approvals
                WHERE id = ? AND record_type = 'approval_request';
                """.strip(),
                (request_id,),
            ).fetchone()
        return row_to_dict(row) if row is not None else None

    def decide(self, request_id: str, approved: bool, *, decision_reason: str = "") -> bool:
        with connect(self.repo_root) as conn, transaction(conn, immediate=True):
            row = conn.execute(
                "SELECT id FROM approvals WHERE id = ? AND status = 'pending';",
                (request_id,),
            ).fetchone()
            if row is None:
                return False
            conn.execute(
                """
                UPDATE approvals
                SET status = ?,
                    decided_at = ?,
                    decision_reason = ?
                WHERE id = ?;
                """.strip(),
                (
                    "approved" if approved else "rejected",
                    _now_iso(),
                    decision_reason.strip(),
                    request_id,
                ),
            )
        return True

    # ------------------------------------------------------------------
    # Action proposals (separate from personal-lane approval flow)
    # ------------------------------------------------------------------

    def create_action_proposal(
        self,
        *,
        action_type: str,
        action_payload: dict[str, Any],
        source: str,
        project_slug: str,
        title: str = "",
    ) -> str:
        proposal_id = uuid.uuid4().hex[:10]
        now = _now_iso()
        payload = action_payload if isinstance(action_payload, dict) else {}
        text = title.strip() or str(payload.get("title", action_type)).strip()
        with connect(self.repo_root) as conn, transaction(conn, immediate=True):
            conn.execute(
                """
                INSERT INTO approvals (
                    id, record_type, lane, project, title, text,
                    action_type, action_payload_json, source, status,
                    created_at, decided_at, decision_reason
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
                """.strip(),
                (
                    proposal_id,
                    "action_proposal",
                    "action",
                    _normalize_project(project_slug),
                    title.strip(),
                    text,
                    action_type.strip(),
                    json.dumps(payload, ensure_ascii=False, sort_keys=True),
                    source.strip(),
                    "pending",
                    now,
                    None,
                    None,
                ),
            )
        return proposal_id

    def list_action_proposals(self, limit: int = 100) -> list[dict[str, Any]]:
        limit = max(1, min(500, int(limit)))
        with connect(self.repo_root) as conn:
            rows = conn.execute(
                """
                SELECT id, record_type, lane, project, title, text,
                       action_type, action_payload_json, source, status,
                       created_at, decided_at, decision_reason
                FROM approvals
                WHERE record_type = 'action_proposal' AND status = 'pending'
                ORDER BY datetime(created_at) DESC, id DESC
                LIMIT ?;
                """.strip(),
                (limit,),
            ).fetchall()
        return [_deserialize_row(row) for row in rows]

    def execute_proposal(
        self,
        proposal_id: str,
        repo_root: Path,
    ) -> dict[str, Any]:
        with connect(self.repo_root) as conn:
            row = conn.execute(
                """
                SELECT id, record_type, lane, project, title, text,
                       action_type, action_payload_json, source, status,
                       created_at, decided_at, decision_reason
                FROM approvals
                WHERE id = ?;
                """.strip(),
                (proposal_id,),
            ).fetchone()
        if row is None:
            return {"ok": False, "message": f"Proposal not found: {proposal_id}"}

        data = _deserialize_row(row)
        if str(data.get("record_type", "")) != "action_proposal":
            return {"ok": False, "message": "Not an action proposal."}
        if str(data.get("status", "")) != "pending":
            return {"ok": False, "message": f"Proposal is already {data.get('status', 'decided')}."}

        from shared_tools.action_executor import ActionExecutor

        executor = ActionExecutor()
        result = executor.execute(
            action_type=str(data.get("action_type", "")),
            payload=data.get("action_payload", {}),
            repo_root=Path(repo_root),
        )

        with connect(self.repo_root) as conn, transaction(conn, immediate=True):
            conn.execute(
                """
                UPDATE approvals
                SET status = ?,
                    decided_at = ?,
                    decision_reason = ?,
                    source = ?
                WHERE id = ? AND status = 'pending';
                """.strip(),
                (
                    "approved",
                    _now_iso(),
                    str(result.get("message", "")).strip(),
                    _append_execution_marker(str(data.get("source", "approval_gate")), bool(result.get("ok", False))),
                    proposal_id,
                ),
            )
        return result


# ----------------------------------------------------------------------
# Helpers
# ----------------------------------------------------------------------

def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _normalize_project(project_slug: str) -> str:
    value = str(project_slug or "").strip()
    return value or "general"


def _append_execution_marker(source: str, execution_ok: bool) -> str:
    suffix = "|executed:ok" if execution_ok else "|executed:error"
    base = source.strip() or "approval_gate"
    return base if suffix in base else f"{base}{suffix}"


def _deserialize_row(row: sqlite3.Row | dict[str, Any]) -> dict[str, Any]:
    data = row_to_dict(row) if isinstance(row, sqlite3.Row) else dict(row)
    data = data or {}
    payload_json = data.get("action_payload_json")
    if isinstance(payload_json, str) and payload_json.strip():
        try:
            data["action_payload"] = json.loads(payload_json)
        except json.JSONDecodeError:
            data["action_payload"] = {}
    else:
        data["action_payload"] = {}
    data.pop("action_payload_json", None)
    if "created_at" in data and "ts" not in data:
        data["ts"] = data["created_at"]
    if data.get("decided_at"):
        data["decided_ts"] = data["decided_at"]
    return data
