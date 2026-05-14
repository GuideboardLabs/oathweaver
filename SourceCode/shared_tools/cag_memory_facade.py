from __future__ import annotations

import re
from dataclasses import dataclass, asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Literal

from cag.memory_store import CAGMemoryStore
from shared_tools.conversation_store import ConversationStore
from shared_tools.topic_memory import TopicMemory

MemoryCategory = Literal["episodic", "semantic", "procedural"]
_TOKEN_RE = re.compile(r"[a-z0-9]{3,}")


def _clean_text(value: Any) -> str:
    return str(value or "").strip()


def _tokens(text: str) -> set[str]:
    return set(_TOKEN_RE.findall(_clean_text(text).lower()))


def _similarity(query: str, text: str) -> float:
    q = _tokens(query)
    if not q:
        return 0.0
    t = _tokens(text)
    if not t:
        return 0.0
    overlap = len(q & t)
    if overlap <= 0:
        return 0.0
    return min(0.75, overlap / max(1.0, float(len(q))))


def _parse_iso(raw: str) -> datetime | None:
    text = _clean_text(raw)
    if not text:
        return None
    try:
        dt = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt


def _recency_bonus(updated_at: str) -> float:
    dt = _parse_iso(updated_at)
    if dt is None:
        return 0.0
    age_days = max(0.0, (datetime.now(timezone.utc) - dt).total_seconds() / 86400.0)
    if age_days <= 1:
        return 0.2
    if age_days <= 7:
        return 0.14
    if age_days <= 30:
        return 0.1
    if age_days <= 180:
        return 0.04
    return 0.0


def _scope_level_to_category(scope_level: str, memory_type: str) -> MemoryCategory:
    scope = str(scope_level or "").strip().lower()
    mtype = str(memory_type or "").strip().lower()
    if scope in {"turn", "thread", "conversation"}:
        return "episodic"
    if mtype in {"constraint", "decision", "lesson", "benchmark_implication"}:
        return "procedural"
    return "semantic"


@dataclass(slots=True)
class MemoryRecord:
    category: MemoryCategory
    key: str
    value: str
    source: str = ""
    source_score: float = 0.0
    updated_at: str = ""
    confidence: float = 0.0
    record_id: str = ""
    conflict_key: str = ""
    meta: dict[str, Any] | None = None

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["source_score"] = round(float(self.source_score or 0.0), 4)
        payload["confidence"] = round(float(self.confidence or 0.0), 4)
        return payload


class CAGMemoryFacade:
    """Canonical typed-recall facade over CAG memory rows."""

    def __init__(self, repo_root: Path) -> None:
        self.repo_root = Path(repo_root)
        self.store = CAGMemoryStore(self.repo_root)
        self.conversation_store = ConversationStore(self.repo_root)
        self.topic_memory = TopicMemory(self.repo_root)

    @staticmethod
    def _status_for_category(category: MemoryCategory) -> list[str]:
        if category == "semantic":
            return ["accepted", "user-confirmed", "benchmark-derived", "watchtower-derived"]
        if category == "procedural":
            return ["accepted", "user-confirmed", "benchmark-derived", "watchtower-derived", "candidate"]
        return ["accepted", "user-confirmed", "candidate"]

    def _rows_for_project(self, project: str) -> list[dict[str, Any]]:
        project_key = str(project or "general").strip() or "general"
        rows = self.store.list_rows_for_projects(
            projects=[project_key, "general"],
            include_expired=False,
            include_superseded=False,
            limit=500,
        )
        return rows

    def _records_from_cag(self, query: str, project: str) -> list[MemoryRecord]:
        out: list[MemoryRecord] = []
        for row in self._rows_for_project(project):
            text = _clean_text(row.get("text", ""))
            if not text:
                continue
            memory_type = str(row.get("type", row.get("memory_type", ""))).strip().lower()
            category = _scope_level_to_category(str(row.get("scope_level", "")), memory_type)
            status = str(row.get("status", "")).strip().lower()
            if status not in set(self._status_for_category(category)):
                continue
            scope = _clean_text(row.get("scope", ""))
            topic = _clean_text(row.get("topic", ""))
            domain = _clean_text(row.get("domain", ""))
            source = _clean_text(row.get("source", "cag_memory"))
            updated_at = _clean_text(row.get("updated_at", ""))
            key = ":".join(part for part in (memory_type, topic or scope, domain) if part) or "memory"
            conflict_key = f"{memory_type}:{topic or scope or key}".strip(":")
            confidence = float(row.get("confidence", 0.0) or 0.0)
            bonus = _recency_bonus(updated_at)
            out.append(
                MemoryRecord(
                    category=category,
                    key=key,
                    value=text,
                    source=source,
                    source_score=bonus,
                    updated_at=updated_at,
                    confidence=confidence,
                    record_id=_clean_text(row.get("memory_id", "")),
                    conflict_key=conflict_key,
                    meta={
                        "status": status,
                        "scope": scope,
                        "scope_level": _clean_text(row.get("scope_level", "")),
                        "domain": domain,
                        "topic": topic,
                        "project": _clean_text(row.get("project", "")),
                        "memory_type": memory_type,
                    },
                )
            )
        return out

    def _episodic_from_conversation(self, query: str, conversation_id: str = "") -> list[MemoryRecord]:
        if not _clean_text(conversation_id):
            return []
        convo = self.conversation_store.get(conversation_id)
        if not isinstance(convo, dict):
            return []
        messages = convo.get("messages") if isinstance(convo.get("messages"), list) else []
        out: list[MemoryRecord] = []
        for msg in messages[-80:]:
            if not isinstance(msg, dict):
                continue
            role = _clean_text(msg.get("role", "")).lower()
            content = _clean_text(msg.get("content", ""))
            ts = _clean_text(msg.get("ts", ""))
            if role not in {"user", "assistant"} or len(content) < 12:
                continue
            out.append(
                MemoryRecord(
                    category="episodic",
                    key=f"conversation:{role}",
                    value=content[:280],
                    source="conversation_store",
                    source_score=_recency_bonus(ts),
                    updated_at=ts,
                    confidence=0.65,
                    record_id=_clean_text(msg.get("id", "")),
                    conflict_key=f"episode:{_clean_text(msg.get('id', ''))}",
                )
            )
        return out

    def _records_from_topic_memory(self, query: str) -> list[MemoryRecord]:
        query_tokens = _tokens(query)
        if not query_tokens:
            return []
        out: list[MemoryRecord] = []
        try:
            topics = self.topic_memory.list_topics()
        except Exception:
            return []
        for meta in topics[:200]:
            if int(meta.get("canon_count", 0) or 0) <= 0:
                continue
            topic_key = _clean_text(meta.get("key", ""))
            if not topic_key:
                continue
            title = _clean_text(meta.get("title", topic_key)) or topic_key
            subtopics = [
                _clean_text(x)
                for x in (meta.get("subtopics", []) if isinstance(meta.get("subtopics", []), list) else [])
                if _clean_text(x)
            ]
            topic_haystack = " ".join([topic_key, title, " ".join(subtopics)])
            topic_tokens = _tokens(topic_haystack)
            overlap = len(query_tokens & topic_tokens)
            if overlap <= 0:
                continue
            try:
                topic = self.topic_memory.get_topic(topic_key) or {}
            except Exception:
                topic = {}
            facts = topic.get("facts", []) if isinstance(topic.get("facts", []), list) else []
            for fact in facts:
                if not isinstance(fact, dict):
                    continue
                if _clean_text(fact.get("status", "")).lower() != "canon":
                    continue
                claim = _clean_text(fact.get("claim", ""))
                if not claim:
                    continue
                updated_at = _clean_text(fact.get("updated_at", "")) or _clean_text(meta.get("updated_at", ""))
                confidence = float(fact.get("confidence", 0.0) or 0.0)
                topicality = min(0.25, float(overlap) / max(1.0, float(len(query_tokens))))
                out.append(
                    MemoryRecord(
                        category="semantic",
                        key=f"topic:{topic_key}",
                        value=claim,
                        source="topic_memory",
                        source_score=topicality + _recency_bonus(updated_at),
                        updated_at=updated_at,
                        confidence=confidence,
                        record_id=_clean_text(fact.get("id", "")),
                        conflict_key=f"topic:{topic_key}:{claim[:80].lower()}",
                        meta={
                            "status": "canon",
                            "topic": title,
                            "topic_key": topic_key,
                            "subtopics": subtopics,
                            "project": _clean_text(fact.get("project", "general")) or "general",
                            "memory_type": "fact",
                        },
                    )
                )
        return out

    @staticmethod
    def resolve_semantic_conflicts(records: list[MemoryRecord]) -> tuple[list[MemoryRecord], list[dict[str, Any]]]:
        grouped: dict[str, list[MemoryRecord]] = {}
        for row in records:
            key = _clean_text(row.conflict_key) or _clean_text(row.key)
            if not key:
                continue
            grouped.setdefault(key, []).append(row)

        resolved: list[MemoryRecord] = []
        conflicts: list[dict[str, Any]] = []
        for key, bucket in grouped.items():
            sorted_rows = sorted(
                bucket,
                key=lambda row: (float(row.source_score) + float(row.confidence), _clean_text(row.updated_at)),
                reverse=True,
            )
            winner = sorted_rows[0]
            resolved.append(winner)
            if len(sorted_rows) > 1:
                conflicts.append(
                    {
                        "conflict_key": key,
                        "winner": winner.to_dict(),
                        "alternatives": [r.to_dict() for r in sorted_rows[1:]],
                    }
                )
        return resolved, conflicts

    def recall(
        self,
        query: str,
        *,
        kinds: tuple[MemoryCategory, ...] = ("semantic", "episodic"),
        k_per_kind: int = 3,
        project: str = "general",
        conversation_id: str = "",
    ) -> dict[str, Any]:
        query_text = _clean_text(query)
        per_kind = max(1, int(k_per_kind or 1))
        kind_set = tuple(k for k in kinds if k in {"semantic", "episodic", "procedural"})
        if not kind_set:
            kind_set = ("semantic", "episodic")

        cag_records = self._records_from_cag(query_text, project)
        semantic_pool = [r for r in cag_records if r.category == "semantic"]
        semantic_pool.extend(self._records_from_topic_memory(query_text))
        episodic_pool = [r for r in cag_records if r.category == "episodic"]
        procedural_pool = [r for r in cag_records if r.category == "procedural"]
        episodic_pool.extend(self._episodic_from_conversation(query_text, conversation_id=conversation_id))

        def _rank(rows: list[MemoryRecord]) -> list[MemoryRecord]:
            scored: list[tuple[float, MemoryRecord]] = []
            for row in rows:
                hay = f"{row.key} {row.value} {row.source}"
                score = _similarity(query_text, hay)
                score += float(row.source_score)
                score += max(0.0, min(0.3, float(row.confidence) * 0.3))
                if score > 0:
                    scored.append((score, row))
            scored.sort(key=lambda item: item[0], reverse=True)
            return [row for _score, row in scored][: max(4, per_kind * 3)]

        semantic_ranked = _rank(semantic_pool) if "semantic" in kind_set else []
        semantic_resolved, conflicts = self.resolve_semantic_conflicts(semantic_ranked)
        semantic_rows = semantic_resolved[:per_kind]
        episodic_rows = (_rank(episodic_pool) if "episodic" in kind_set else [])[:per_kind]
        procedural_rows = (_rank(procedural_pool) if "procedural" in kind_set else [])[:per_kind]

        return {
            "query": query_text,
            "k_per_kind": per_kind,
            "results": {
                "semantic": [r.to_dict() for r in semantic_rows],
                "episodic": [r.to_dict() for r in episodic_rows],
                "procedural": [r.to_dict() for r in procedural_rows],
            },
            "conflicts": conflicts,
        }
