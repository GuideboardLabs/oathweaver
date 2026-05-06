from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from pathlib import Path
from threading import Lock
from typing import Any


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


class HandoffQueue:
    AUTHORIZED_ACTOR = "orchestrator"
    INCOMPLETE_TOKEN = "__OATHWEAVER_OUTBOX_INCOMPLETE__"

    def __init__(self, repo_root: Path) -> None:
        self.root = repo_root / "Runtime" / "handoff"
        self.pending_dir = self.root / "pending"
        self.denied_dir = self.root / "denied"
        self.inbox_dirs = {
            "codex": self.root / "codex" / "inbox",
        }
        self.outbox_dirs = {
            "codex": self.root / "codex" / "outbox",
        }
        self.processed_dirs = {
            "codex": self.root / "codex" / "outbox_processed",
        }

        self.pending_dir.mkdir(parents=True, exist_ok=True)
        self.denied_dir.mkdir(parents=True, exist_ok=True)
        for folder in [*self.inbox_dirs.values(), *self.outbox_dirs.values(), *self.processed_dirs.values()]:
            folder.mkdir(parents=True, exist_ok=True)

        self.lock = Lock()
        self.sync_outbox_placeholders()

    def _assert_authorized(self, actor: str) -> None:
        if actor.strip().lower() != self.AUTHORIZED_ACTOR:
            raise PermissionError("Only orchestrator is authorized to finalize inbox handoffs.")

    def _pending_path(self, request_id: str) -> Path:
        return self.pending_dir / f"{request_id}.json"

    def _target_inbox(self, target: str) -> Path | None:
        return self.inbox_dirs.get(target.lower())

    def _target_outbox(self, target: str) -> Path | None:
        return self.outbox_dirs.get(target.lower())

    def _target_processed(self, target: str) -> Path | None:
        return self.processed_dirs.get(target.lower())

    def _load_json(self, path: Path) -> dict[str, Any] | None:
        if not path.exists():
            return None
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            return None

    def _outbox_placeholder_path(self, *, target: str, request_id: str) -> Path | None:
        outbox = self._target_outbox(target)
        if outbox is None:
            return None
        return outbox / f"{request_id}.md"

    def _processed_file_for(self, *, target: str, request_id: str) -> Path | None:
        processed = self._target_processed(target)
        if processed is None:
            return None
        exact = processed / f"{request_id}.md"
        if exact.exists():
            return exact
        matches = sorted(processed.glob(f"{request_id}_*"), key=lambda p: p.stat().st_mtime, reverse=True)
        if matches:
            return matches[0]
        return None

    def _placeholder_text(self, row: dict[str, Any], inbox_path: Path) -> str:
        request_id = str(row.get("id", "")).strip()
        target = str(row.get("target", "")).strip().lower()
        project = str(row.get("project", "")).strip()
        request_text = str(row.get("request_text", "")).strip()
        return (
            "OATHWEAVER OUTBOX PLACEHOLDER\n"
            "STATUS: INCOMPLETE\n"
            f"THREAD_ID: {request_id}\n"
            f"TARGET: {target}\n"
            f"PROJECT: {project}\n"
            f"SOURCE_INBOX_FILE: {str(inbox_path)}\n"
            f"TOKEN: {self.INCOMPLETE_TOKEN}\n\n"
            "INSTRUCTIONS:\n"
            "1) Replace this template with your final response.\n"
            f"2) Remove the token string: {self.INCOMPLETE_TOKEN}\n"
            "3) Save file in-place; then run /learn-outbox <target> [lane] [n].\n\n"
            "REQUEST:\n"
            f"{request_text}\n\n"
            "FINAL_RESPONSE:\n"
            f"{self.INCOMPLETE_TOKEN}\n"
        )

    def _extract_outbox_response(self, raw_text: str) -> tuple[str, bool]:
        marker = "FINAL_RESPONSE:"
        body = raw_text.strip()
        if marker in raw_text:
            body = raw_text.split(marker, 1)[1].strip()
        is_incomplete = (not body) or (self.INCOMPLETE_TOKEN in body)
        return body, is_incomplete

    def sync_outbox_placeholders(self) -> dict[str, int]:
        created = 0
        scanned = 0
        removed_stale = 0
        with self.lock:
            for target, inbox in self.inbox_dirs.items():
                for path in inbox.glob("*.json"):
                    row = self._load_json(path)
                    if row is None:
                        continue
                    request_id = str(row.get("id", "")).strip()
                    if not request_id:
                        continue
                    scanned += 1
                    placeholder = self._outbox_placeholder_path(target=target, request_id=request_id)
                    processed = self._processed_file_for(target=target, request_id=request_id)
                    if processed is not None:
                        if placeholder is not None and placeholder.exists():
                            placeholder.unlink(missing_ok=True)
                            removed_stale += 1
                        continue
                    if placeholder is None or placeholder.exists():
                        continue
                    placeholder.write_text(self._placeholder_text(row, path), encoding="utf-8")
                    created += 1
        return {"scanned": scanned, "created": created, "removed_stale": removed_stale}

    def monitor_threads(self, limit: int = 100) -> list[dict[str, Any]]:
        limit = max(1, min(limit, 500))
        self.sync_outbox_placeholders()
        rows: list[dict[str, Any]] = []
        with self.lock:
            for target, inbox in self.inbox_dirs.items():
                for path in inbox.glob("*.json"):
                    row = self._load_json(path)
                    if row is None:
                        continue
                    request_id = str(row.get("id", "")).strip()
                    if not request_id:
                        continue

                    outbox = self._outbox_placeholder_path(target=target, request_id=request_id)
                    processed = self._processed_file_for(target=target, request_id=request_id)
                    status = "missing_outbox"
                    incomplete = False
                    outbox_path = ""

                    if outbox is not None and outbox.exists():
                        outbox_path = str(outbox)
                        try:
                            text = outbox.read_text(encoding="utf-8")
                        except UnicodeDecodeError:
                            text = outbox.read_text(encoding="utf-8-sig")
                        _, incomplete = self._extract_outbox_response(text)
                        status = "waiting_output" if incomplete else "ready_for_ingest"

                    if processed is not None:
                        status = "processed"

                    rows.append(
                        {
                            "id": request_id,
                            "target": target,
                            "project": str(row.get("project", "")),
                            "created_at": str(row.get("created_at", "")),
                            "updated_at": str(row.get("updated_at", "")),
                            "request_text": str(row.get("request_text", "")),
                            "inbox_path": str(path),
                            "outbox_path": outbox_path,
                            "processed_path": str(processed) if processed is not None else "",
                            "status": status,
                            "placeholder_incomplete": incomplete,
                        }
                    )
        rows.sort(key=lambda r: str(r.get("created_at", "")), reverse=True)
        return rows[:limit]

    def monitor_text(self, limit: int = 50) -> str:
        rows = self.monitor_threads(limit=limit)
        if not rows:
            return "No inbox threads found."
        lines = [f"Handoff monitor ({len(rows)} shown):"]
        for row in rows:
            lines.append(
                f"- {row.get('id','')} | target={row.get('target','')} | status={row.get('status','')} | "
                f"outbox={row.get('outbox_path','') or 'none'}"
            )
        return "\n".join(lines)

    def create_pending(self, target: str, request_text: str, project_slug: str) -> dict[str, Any]:
        target_key = target.lower().strip()
        inbox_dir = self._target_inbox(target_key)
        if inbox_dir is None:
            raise ValueError(f"Invalid target '{target}'. Use 'codex'.")
        if not request_text.strip():
            raise ValueError("Request text cannot be empty.")

        request_id = uuid.uuid4().hex[:10]
        payload = {
            "id": request_id,
            "target": target_key,
            "status": "pending",
            "finalization_authority": self.AUTHORIZED_ACTOR,
            "project": project_slug,
            "request_text": request_text.strip(),
            "created_at": _now_iso(),
            "updated_at": _now_iso(),
        }

        with self.lock:
            self._pending_path(request_id).write_text(json.dumps(payload, indent=2), encoding="utf-8")

        return payload

    def list_pending(self) -> list[dict[str, Any]]:
        with self.lock:
            out: list[dict[str, Any]] = []
            for path in self.pending_dir.glob("*.json"):
                data = self._load_json(path)
                if data is None:
                    continue
                out.append(data)
            out.sort(key=lambda row: str(row.get("created_at", "")), reverse=True)
            return out

    def approve(self, request_id: str, reason: str = "", actor: str = AUTHORIZED_ACTOR) -> dict[str, Any] | None:
        self._assert_authorized(actor)
        with self.lock:
            pending_path = self._pending_path(request_id)
            data = self._load_json(pending_path)
            if data is None:
                return None

            target = str(data.get("target", "")).lower()
            inbox = self._target_inbox(target)
            if inbox is None:
                return None

            data["status"] = "approved"
            data["decision_reason"] = reason.strip()
            data["finalized_by"] = actor.strip().lower()
            data["decided_at"] = _now_iso()
            data["updated_at"] = _now_iso()

            out_path = inbox / f"{request_id}.json"
            out_path.write_text(json.dumps(data, indent=2), encoding="utf-8")
            pending_path.unlink(missing_ok=True)

            placeholder = self._outbox_placeholder_path(target=target, request_id=request_id)
            if placeholder is not None and not placeholder.exists():
                placeholder.write_text(self._placeholder_text(data, out_path), encoding="utf-8")

            data["outbox_path"] = str(out_path)
            return data

    def deny(self, request_id: str, reason: str, actor: str = AUTHORIZED_ACTOR) -> dict[str, Any] | None:
        self._assert_authorized(actor)
        with self.lock:
            pending_path = self._pending_path(request_id)
            data = self._load_json(pending_path)
            if data is None:
                return None

            data["status"] = "denied"
            data["decision_reason"] = reason.strip()
            data["finalized_by"] = actor.strip().lower()
            data["decided_at"] = _now_iso()
            data["updated_at"] = _now_iso()

            denied_path = self.denied_dir / f"{request_id}.json"
            denied_path.write_text(json.dumps(data, indent=2), encoding="utf-8")
            pending_path.unlink(missing_ok=True)

            data["denied_path"] = str(denied_path)
            return data

    def list_inbox(self, target: str) -> list[dict[str, Any]]:
        target_key = target.lower().strip()
        inbox = self._target_inbox(target_key)
        if inbox is None:
            raise ValueError(f"Invalid target '{target}'. Use 'codex'.")

        with self.lock:
            out: list[dict[str, Any]] = []
            for path in inbox.glob("*.json"):
                data = self._load_json(path)
                if data is None:
                    continue
                data["file_path"] = str(path)
                out.append(data)
            out.sort(key=lambda row: str(row.get("created_at", "")), reverse=True)
            return out

    def count_pending(self) -> int:
        return len(self.list_pending())
