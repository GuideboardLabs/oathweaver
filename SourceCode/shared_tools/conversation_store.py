from __future__ import annotations

import json
import re
import uuid
from datetime import datetime, timezone
from pathlib import Path
from threading import Lock
from typing import Any


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _clean_title(text: str) -> str:
    compact = " ".join(text.strip().split())
    if not compact:
        return "New Chat"
    return compact if len(compact) <= 64 else f"{compact[:61]}..."


def _is_default_auto_title(text: str) -> bool:
    title = _clean_title(str(text or ""))
    return title in {"New Chat", "General Chat"}


def _clean_project(text: str) -> str:
    compact = "_".join(text.strip().split())
    if not compact:
        return "general"
    return compact.lower()


def _clean_topic_id(value: Any) -> str:
    compact = str(value or "").strip()
    return compact or "general"


def _clean_image_style(value: Any) -> str:
    style = str(value or "").strip().lower()
    if style in {"realistic", "lora"}:
        return style
    return "realistic"


def _clean_selected_loras(value: Any) -> list[str]:
    raw_items = value if isinstance(value, (list, tuple, set)) else []
    seen: set[str] = set()
    out: list[str] = []
    for item in raw_items:
        text = str(item or "").strip()
        if not text or text in seen:
            continue
        seen.add(text)
        out.append(text[:220])
        if len(out) >= 32:
            break
    return out


def _slugify(text: str) -> str:
    slug = re.sub(r"[^\w\s-]", "", text.lower().strip())
    return re.sub(r"[\s_-]+", "_", slug).strip("_")[:60]


def _first_user_title_candidate(messages: Any) -> str:
    rows = messages if isinstance(messages, list) else []
    for row in rows:
        if str((row or {}).get("role", "")).strip().lower() != "user":
            continue
        raw = str((row or {}).get("content", "")).strip()
        if raw.startswith("/talk "):
            raw = raw[len("/talk ") :].strip()
        if not raw or raw.startswith("/"):
            continue
        return _clean_title(raw)
    return ""


def _infer_title_manually_set(data: dict[str, Any]) -> bool:
    stored = data.get("title_manually_set")
    if isinstance(stored, bool):
        return stored
    title = _clean_title(str(data.get("title", "New Chat")))
    if _is_default_auto_title(title):
        return False
    first_user_title = _first_user_title_candidate(data.get("messages", []))
    if first_user_title and title == first_user_title:
        return False
    return True


def _atomic_write_text(path: Path, content: str) -> None:
    tmp_path = path.with_suffix(f"{path.suffix}.tmp")
    tmp_path.write_text(content, encoding="utf-8")
    tmp_path.replace(path)


class ConversationStore:
    def __init__(self, repo_root: Path, user_id: str | None = None) -> None:
        uid = str(user_id or "").strip()
        if uid:
            self.root = repo_root / "Runtime" / "users" / uid / "conversations"
        else:
            self.root = repo_root / "Runtime" / "conversations"
        self.root.mkdir(parents=True, exist_ok=True)
        self.lock = Lock()

    def _path_for(self, conversation_id: str) -> Path:
        return self.root / f"{conversation_id}.json"

    def _load(self, conversation_id: str) -> dict[str, Any] | None:
        path = self._path_for(conversation_id)
        if not path.exists():
            return None
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            return None

    def _save(self, data: dict[str, Any]) -> None:
        path = self._path_for(str(data["id"]))
        _atomic_write_text(path, json.dumps(data, indent=2, ensure_ascii=True))

    @staticmethod
    def _read_index(messages: list[dict[str, Any]], last_read_message_id: str) -> int:
        needle = str(last_read_message_id or "").strip()
        if not needle:
            return -1
        for idx in range(len(messages) - 1, -1, -1):
            if str(messages[idx].get("id", "")).strip() == needle:
                return idx
        return -1

    @classmethod
    def _assistant_unread_count(cls, data: dict[str, Any]) -> int:
        messages = data.get("messages") if isinstance(data.get("messages"), list) else []
        read_idx = cls._read_index(messages, str(data.get("last_read_message_id", "")).strip())
        unread = 0
        for idx, row in enumerate(messages):
            if idx <= read_idx:
                continue
            if str((row or {}).get("role", "")).strip().lower() == "assistant":
                unread += 1
        return unread

    @classmethod
    def _decorate(cls, data: dict[str, Any]) -> dict[str, Any]:
        if not str(data.get("topic_id", "")).strip():
            data["topic_id"] = "general" if str(data.get("project", "general")).strip() == "general" else ""
        data["path"] = str(data.get("path", "")).strip()
        data["title_manually_set"] = _infer_title_manually_set(data)
        data["image_style"] = _clean_image_style(data.get("image_style", "realistic"))
        data["selected_loras"] = _clean_selected_loras(data.get("selected_loras", []))
        if data["selected_loras"] and data["image_style"] == "realistic":
            data["image_style"] = "lora"
        unread_count = cls._assistant_unread_count(data)
        data["last_read_message_id"] = str(data.get("last_read_message_id", "")).strip()
        data["unread_count"] = unread_count
        data["has_unread"] = unread_count > 0
        return data

    def _generate_path(self, topic_slug: str, title: str) -> str:
        if not topic_slug or topic_slug == "general":
            return ""
        title_slug = _slugify(title) or "untitled"
        base = f"/{topic_slug}/{title_slug}"
        existing: set[str] = set()
        for path in self.root.glob("*.json"):
            try:
                data = json.loads(path.read_text(encoding="utf-8"))
                p = str(data.get("path", "")).strip()
                if p:
                    existing.add(p)
            except (json.JSONDecodeError, OSError):
                continue
        if base not in existing:
            return base
        for i in range(2, 100):
            candidate = f"{base}_{i}"
            if candidate not in existing:
                return candidate
        return f"{base}_{uuid.uuid4().hex[:6]}"

    def create(self, title: str = "New Chat", project: str = "general", topic_id: str = "general", path: str = "") -> dict[str, Any]:
        with self.lock:
            now = _now_iso()
            conversation_id = uuid.uuid4().hex[:12]
            clean_title = _clean_title(title)
            data = {
                "id": conversation_id,
                "title": clean_title,
                "project": _clean_project(project),
                "topic_id": _clean_topic_id(topic_id),
                "path": str(path).strip(),
                "created_at": now,
                "updated_at": now,
                "summary": "",
                "messages": [],
                "last_read_message_id": "",
                "title_manually_set": not _is_default_auto_title(clean_title),
                "image_style": "realistic",
                "selected_loras": [],
            }
            self._save(data)
            return self._decorate(data)

    def get(self, conversation_id: str) -> dict[str, Any] | None:
        with self.lock:
            data = self._load(conversation_id)
            if data is None:
                return None
            return self._decorate(data)

    def rename(self, conversation_id: str, title: str, *, manual: bool = True) -> dict[str, Any] | None:
        with self.lock:
            data = self._load(conversation_id)
            if data is None:
                return None
            data["title"] = _clean_title(title)
            data["title_manually_set"] = bool(manual)
            data["updated_at"] = _now_iso()
            self._save(data)
            return self._decorate(data)

    def set_project(self, conversation_id: str, project: str) -> dict[str, Any] | None:
        with self.lock:
            data = self._load(conversation_id)
            if data is None:
                return None
            data["project"] = _clean_project(project)
            data["updated_at"] = _now_iso()
            self._save(data)
            return self._decorate(data)

    def set_path(self, conversation_id: str, path: str) -> dict[str, Any] | None:
        with self.lock:
            data = self._load(conversation_id)
            if data is None:
                return None
            data["path"] = str(path).strip()
            data["updated_at"] = _now_iso()
            self._save(data)
            return self._decorate(data)

    def set_topic(self, conversation_id: str, topic_id: str) -> dict[str, Any] | None:
        with self.lock:
            data = self._load(conversation_id)
            if data is None:
                return None
            data["topic_id"] = _clean_topic_id(topic_id)
            data["updated_at"] = _now_iso()
            self._save(data)
            return self._decorate(data)

    def set_image_preferences(
        self,
        conversation_id: str,
        *,
        image_style: str | None = None,
        selected_loras: list[str] | None = None,
    ) -> dict[str, Any] | None:
        with self.lock:
            data = self._load(conversation_id)
            if data is None:
                return None

            if image_style is not None:
                cleaned_style = _clean_image_style(image_style)
                data["image_style"] = cleaned_style
                if cleaned_style == "realistic" and selected_loras is None:
                    data["selected_loras"] = []

            if selected_loras is not None:
                cleaned_loras = _clean_selected_loras(selected_loras)
                data["selected_loras"] = cleaned_loras
                if cleaned_loras:
                    data["image_style"] = "lora"
                elif image_style is None and str(data.get("image_style", "")).strip().lower() == "lora":
                    data["image_style"] = "realistic"

            data["updated_at"] = _now_iso()
            self._save(data)
            return self._decorate(data)

    def delete(self, conversation_id: str) -> bool:
        with self.lock:
            path = self._path_for(conversation_id)
            if not path.exists():
                return False
            path.unlink(missing_ok=True)
            return True

    def add_message(
        self,
        conversation_id: str,
        role: str,
        content: str,
        mode: str | None = None,
        attachments: list[dict[str, Any]] | None = None,
        foraging: bool | None = None,
        building: bool | None = None,
        request_id: str | None = None,
        meta: dict[str, Any] | None = None,
        reply_to: dict[str, Any] | None = None,
    ) -> dict[str, Any] | None:
        with self.lock:
            data = self._load(conversation_id)
            if data is None:
                return None

            message = {
                "id": uuid.uuid4().hex[:10],
                "role": role,
                "content": content,
                "ts": _now_iso(),
            }
            if mode:
                message["mode"] = str(mode).strip().lower()
            if foraging is not None:
                message["foraging"] = bool(foraging)
            if building is not None:
                message["building"] = bool(building)
            if request_id:
                message["request_id"] = str(request_id).strip()
            if attachments:
                safe_attachments: list[dict[str, Any]] = []
                for item in attachments:
                    if not isinstance(item, dict):
                        continue
                    row = {
                        "id": str(item.get("id", "")).strip(),
                        "type": str(item.get("type", "")).strip().lower() or "file",
                        "name": str(item.get("name", "")).strip(),
                        "filename": str(item.get("filename", "")).strip(),
                        "mime": str(item.get("mime", "")).strip().lower(),
                        "url": str(item.get("url", "")).strip(),
                        "size": int(item.get("size", 0)) if str(item.get("size", "")).strip() else 0,
                        "model_family": str(item.get("model_family", "")).strip().lower(),
                    }
                    safe_attachments.append(row)
                if safe_attachments:
                    message["attachments"] = safe_attachments
            if meta and isinstance(meta, dict):
                message["meta"] = {k: v for k, v in meta.items() if v is not None}
            if reply_to and isinstance(reply_to, dict):
                message["reply_to"] = {
                    "id": str(reply_to.get("id", "")).strip(),
                    "role": str(reply_to.get("role", "")).strip(),
                    "excerpt": str(reply_to.get("excerpt", ""))[:300].strip(),
                }
            data["messages"].append(message)
            data["updated_at"] = _now_iso()

            current_title = _clean_title(str(data.get("title", "New Chat")))
            manual_title = _infer_title_manually_set(data)
            if role == "user" and not manual_title and _is_default_auto_title(current_title):
                raw = content.strip()
                if raw.startswith("/talk "):
                    raw = raw[len("/talk ") :].strip()
                if raw and not raw.startswith("/"):
                    data["title"] = _clean_title(raw)
                    data["title_manually_set"] = False

            self._save(data)
            return message

    def set_message_feedback(
        self,
        conversation_id: str,
        message_id: str,
        *,
        rating: str = "",
        disregard: bool = False,
    ) -> dict[str, Any] | None:
        normalized_id = str(message_id or "").strip()
        if not normalized_id:
            return None
        normalized_rating = str(rating or "").strip().lower()
        if normalized_rating not in {"", "up", "down"}:
            normalized_rating = ""
        with self.lock:
            data = self._load(conversation_id)
            if data is None:
                return None
            messages = data.get("messages") if isinstance(data.get("messages"), list) else []
            target: dict[str, Any] | None = None
            for row in messages:
                if not isinstance(row, dict):
                    continue
                if str(row.get("id", "")).strip() != normalized_id:
                    continue
                target = row
                break
            if target is None:
                return None

            if normalized_rating or disregard:
                target["feedback"] = {
                    "rating": normalized_rating,
                    "disregard": bool(disregard),
                    "updated_at": _now_iso(),
                }
            else:
                target.pop("feedback", None)

            meta = target.get("meta")
            if not isinstance(meta, dict):
                meta = {}
                target["meta"] = meta
            if bool(disregard):
                meta["disregard_context"] = True
            else:
                meta.pop("disregard_context", None)
            if normalized_rating:
                meta["feedback_rating"] = normalized_rating
            else:
                meta.pop("feedback_rating", None)
            if not meta:
                target.pop("meta", None)

            data["updated_at"] = _now_iso()
            self._save(data)
            return target

    def replace_messages(
        self,
        conversation_id: str,
        messages: list[dict[str, Any]] | None,
        *,
        summary: str | None = None,
        last_read_message_id: str | None = None,
    ) -> dict[str, Any] | None:
        with self.lock:
            data = self._load(conversation_id)
            if data is None:
                return None
            safe_messages: list[dict[str, Any]] = []
            for row in messages or []:
                if isinstance(row, dict):
                    safe_messages.append(json.loads(json.dumps(row, ensure_ascii=True)))
            data["messages"] = safe_messages
            if summary is not None:
                data["summary"] = str(summary).strip()[:600]
            if last_read_message_id is not None:
                data["last_read_message_id"] = str(last_read_message_id or "").strip()
            data["updated_at"] = _now_iso()
            self._save(data)
            return self._decorate(data)

    def mark_read(self, conversation_id: str) -> dict[str, Any] | None:
        with self.lock:
            data = self._load(conversation_id)
            if data is None:
                return None
            messages = data.get("messages") if isinstance(data.get("messages"), list) else []
            if messages:
                data["last_read_message_id"] = str(messages[-1].get("id", "")).strip()
            else:
                data["last_read_message_id"] = ""
            self._save(data)
            return self._decorate(data)

    def update_summary(self, conversation_id: str, summary: str) -> None:
        with self.lock:
            data = self._load(conversation_id)
            if data is None:
                return
            data["summary"] = str(summary).strip()[:600]
            data["updated_at"] = _now_iso()
            self._save(data)

    def get_summary(self, conversation_id: str) -> str:
        with self.lock:
            data = self._load(conversation_id)
            if data is None:
                return ""
            return str(data.get("summary", ""))

    def list(self) -> list[dict[str, Any]]:
        with self.lock:
            items: list[dict[str, Any]] = []
            for path in self.root.glob("*.json"):
                try:
                    data = json.loads(path.read_text(encoding="utf-8"))
                except json.JSONDecodeError:
                    continue
                messages = data.get("messages") or []
                last_preview = ""
                if messages:
                    content = str(messages[-1].get("content", ""))
                    low = content.lower().strip()
                    if low == "/talk":
                        content = ""
                    elif low.startswith("/talk "):
                        content = content[6:]
                    compact = " ".join(content.split())
                    last_preview = compact[:90]
                summary_raw = str(data.get("summary", ""))
                unread_count = self._assistant_unread_count(data)
                items.append(
                    {
                        "id": data.get("id", path.stem),
                        "title": data.get("title", "New Chat"),
                        "project": data.get("project", "general"),
                        "topic_id": data.get("topic_id", "general" if str(data.get("project", "general")).strip() == "general" else ""),
                        "path": str(data.get("path", "")).strip(),
                        "created_at": data.get("created_at", ""),
                        "updated_at": data.get("updated_at", ""),
                        "message_count": len(messages),
                        "last_preview": last_preview,
                        "summary": summary_raw[:200],
                        "last_read_message_id": str(data.get("last_read_message_id", "")).strip(),
                        "title_manually_set": _infer_title_manually_set(data),
                        "unread_count": unread_count,
                        "has_unread": unread_count > 0,
                    }
                )
            items.sort(key=lambda item: str(item.get("updated_at", "")), reverse=True)
            return items
