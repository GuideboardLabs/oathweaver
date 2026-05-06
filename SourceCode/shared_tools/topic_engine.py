from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from pathlib import Path
from threading import Lock
from typing import Any


VALID_TOPIC_TYPES: frozenset[str] = frozenset({
    "computer_science_programming",
    "mathematics",
    "science",
    "history",
    "writing_rhetoric",
    "business_strategy",
    "law_policy",
    "engineering",
    "creative",
    "general_research",
})


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _slug_from_name(name: str) -> str:
    return "_".join(str(name).strip().lower().split())[:48] or "topic"


def _atomic_write(path: Path, data: Any) -> None:
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(data, indent=2, ensure_ascii=True), encoding="utf-8")
    tmp.replace(path)


class TopicEngine:
    def __init__(self, repo_root: Path) -> None:
        self.repo_root = Path(repo_root)
        self.topics_dir = self.repo_root / "Runtime" / "topics"
        self.topics_path = self.topics_dir / "topics.json"
        self._lock = Lock()
        self.topics_dir.mkdir(parents=True, exist_ok=True)
        if not self.topics_path.exists():
            self.topics_path.write_text("[]", encoding="utf-8")

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _load(self) -> list[dict[str, Any]]:
        try:
            data = json.loads(self.topics_path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            return []
        return [x for x in data if isinstance(x, dict)] if isinstance(data, list) else []

    def _save(self, topics: list[dict[str, Any]]) -> None:
        _atomic_write(self.topics_path, topics)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def list_topics(self, parent_id: str = "") -> list[dict[str, Any]]:
        """Return top-level topics when parent_id is empty, sub-topics of a parent otherwise."""
        with self._lock:
            topics = self._load()
            key = str(parent_id).strip()
            return [t for t in topics if str(t.get("parent_id", "")).strip() == key]

    def get_topic(self, topic_id: str) -> dict[str, Any] | None:
        key = str(topic_id).strip()
        with self._lock:
            topics = self._load()
            return next((t for t in topics if str(t.get("id", "")) == key), None)

    def get_by_slug(self, slug: str) -> dict[str, Any] | None:
        key = str(slug).strip().lower()
        with self._lock:
            topics = self._load()
            return next((t for t in topics if str(t.get("slug", "")) == key), None)

    def create_topic(
        self,
        name: str,
        type: str,
        description: str,
        seed_question: str,
        parent_id: str = "",
    ) -> dict[str, Any]:
        name = str(name).strip()
        if not name:
            raise ValueError("Topic name cannot be empty.")
        topic_type = str(type).strip().lower()
        if topic_type not in VALID_TOPIC_TYPES:
            raise ValueError(f"Invalid topic type: '{topic_type}'. Must be one of: {sorted(VALID_TOPIC_TYPES)}")
        description = str(description).strip()
        if len(description) < 50:
            raise ValueError("Topic description must be at least 50 characters.")
        seed_question = str(seed_question).strip()
        if not seed_question:
            raise ValueError("Seed question cannot be empty.")
        parent_id = str(parent_id).strip()

        slug = _slug_from_name(name)
        now = _now_iso()
        topic: dict[str, Any] = {
            "id": f"topic_{uuid.uuid4().hex[:10]}",
            "name": name,
            "slug": slug,
            "type": topic_type,
            "description": description,
            "seed_question": seed_question,
            "parent_id": parent_id,
            "created_at": now,
            "updated_at": now,
        }
        with self._lock:
            topics = self._load()
            topics.append(topic)
            self._save(topics)
        return topic

    def update_topic(self, topic_id: str, **fields: Any) -> dict[str, Any] | None:
        key = str(topic_id).strip()
        allowed = {"name", "description", "seed_question", "type"}
        with self._lock:
            topics = self._load()
            hit: dict[str, Any] | None = None
            for t in topics:
                if str(t.get("id", "")) != key:
                    continue
                for field, value in fields.items():
                    if field not in allowed:
                        continue
                    if field == "name":
                        value = str(value).strip()
                        if value:
                            t["slug"] = _slug_from_name(value)
                    elif field == "type":
                        value = str(value).strip().lower()
                        if value not in VALID_TOPIC_TYPES:
                            continue
                    elif field == "description":
                        value = str(value).strip()
                        if len(value) < 50:
                            continue
                    elif field == "seed_question":
                        value = str(value).strip()
                    t[field] = value
                t["updated_at"] = _now_iso()
                hit = t
                break
            if hit is None:
                return None
            self._save(topics)
        return hit

    def delete_topic(self, topic_id: str) -> bool:
        key = str(topic_id).strip()
        with self._lock:
            topics = self._load()
            # Remove topic and all its sub-topics
            new_topics = [t for t in topics if str(t.get("id", "")) != key and str(t.get("parent_id", "")) != key]
            if len(new_topics) == len(topics):
                return False
            self._save(new_topics)
        return True
