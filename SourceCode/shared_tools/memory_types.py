from __future__ import annotations

import re
from dataclasses import dataclass, asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Literal
from urllib.parse import urlsplit

from shared_tools.conversation_store import ConversationStore
from shared_tools.domain_reputation import DomainReputation
from shared_tools.project_context_memory import ProjectContextMemory
from shared_tools.topic_memory import TopicMemory

MemoryCategory = Literal["episodic", "semantic", "procedural"]


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


def _clean_text(value: Any) -> str:
    return str(value or "").strip()


def _tokens(text: str) -> set[str]:
    return set(re.findall(r"[a-z0-9]{3,}", _clean_text(text).lower()))


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


def _recency_score(updated_at: str) -> float:
    dt = _parse_iso(updated_at)
    if dt is None:
        return 0.0
    age_days = max(0.0, (datetime.now(timezone.utc) - dt).total_seconds() / 86400.0)
    if age_days <= 1:
        return 0.18
    if age_days <= 7:
        return 0.12
    if age_days <= 30:
        return 0.08
    if age_days <= 180:
        return 0.03
    return 0.0


def _domain_hint(text: str) -> str:
    body = _clean_text(text)
    if not body:
        return ""
    if "//" in body:
        try:
            return str(urlsplit(body).hostname or "").lower().removeprefix("www.")
        except Exception:
            return ""
    m = re.search(r"\b([a-z0-9-]+\.[a-z]{2,})(?:/|\b)", body.lower())
    return m.group(1) if m else ""


class TypedMemoryFacade:
    """Mem0-style memory typing over existing local stores."""

    def __init__(
        self,
        repo_root: Path,
        *,
        topic_memory: TopicMemory | None = None,
        project_memory: ProjectContextMemory | None = None,
        conversation_store: ConversationStore | None = None,
        domain_reputation: DomainReputation | None = None,
    ) -> None:
        self.repo_root = Path(repo_root)
        self.topic_memory = topic_memory or TopicMemory(self.repo_root)
        self.project_memory = project_memory or ProjectContextMemory(self.repo_root)
        self.conversation_store = conversation_store or ConversationStore(self.repo_root)
        self.domain_reputation = domain_reputation or DomainReputation(self.repo_root)

    def _similarity(self, query: str, text: str) -> float:
        q = _tokens(query)
        if not q:
            return 0.0
        t = _tokens(text)
        if not t:
            return 0.0
        overlap = len(q & t)
        if overlap <= 0:
            return 0.0
        return min(0.45, overlap / max(1.0, float(len(q))))

    def _source_score(self, source: str, updated_at: str = "") -> float:
        domain = _domain_hint(source)
        rep = 0.0
        if domain:
            try:
                rep = float(self.domain_reputation.get_adjustment(domain))
            except Exception:
                rep = 0.0
        return float(rep) + _recency_score(updated_at)

    def _personal_records(self) -> list[dict[str, Any]]:
        return []

    def _semantic_from_project(self, project: str) -> list[MemoryRecord]:
        rows = self.project_memory.export_project_rows(project)
        out: list[MemoryRecord] = []
        for row in rows:
            key = _clean_text(row.get("fact_key", ""))
            value = _clean_text(row.get("fact_value", ""))
            if not key or not value:
                continue
            source = _clean_text(row.get("source", "project_facts"))
            updated_at = _clean_text(row.get("updated_at", ""))
            out.append(
                MemoryRecord(
                    category="semantic",
                    key=key,
                    value=value,
                    source=source,
                    source_score=self._source_score(source, updated_at),
                    updated_at=updated_at,
                    confidence=0.72,
                    conflict_key=f"project:{key}",
                )
            )
        return out

    def _semantic_from_topics(self, query: str) -> list[MemoryRecord]:
        out: list[MemoryRecord] = []
        query_terms = _tokens(query)
        if not query_terms:
            return out
        try:
            topics = self.topic_memory.list_topics()[:10]
        except Exception:
            topics = []
        for entry in topics:
            key = _clean_text(entry.get("key", ""))
            title = _clean_text(entry.get("title", ""))
            descriptor = f"{key} {title} {' '.join(entry.get('subtopics', []) if isinstance(entry.get('subtopics', []), list) else [])}"
            if self._similarity(query, descriptor) <= 0:
                continue
            try:
                topic = self.topic_memory.get_topic(key) if key else None
            except Exception:
                topic = None
            if not isinstance(topic, dict):
                continue
            for fact in topic.get("facts", []):
                if not isinstance(fact, dict) or str(fact.get("status", "")).strip().lower() != "canon":
                    continue
                claim = _clean_text(fact.get("claim", ""))
                if not claim:
                    continue
                updated_at = _clean_text(fact.get("updated_at", topic.get("updated_at", "")))
                source = _clean_text(fact.get("source_file", "topic_memory")) or "topic_memory"
                out.append(
                    MemoryRecord(
                        category="semantic",
                        key=f"topic:{title or key}",
                        value=claim,
                        source=source,
                        source_score=self._source_score(source, updated_at),
                        updated_at=updated_at,
                        confidence=float(fact.get("confidence", 0.7) or 0.7),
                        record_id=_clean_text(fact.get("id", "")),
                        conflict_key=f"topic:{key}:{_clean_text(fact.get('id', ''))}",
                    )
                )
        return out

    def _semantic_from_personal(self) -> list[MemoryRecord]:
        out: list[MemoryRecord] = []
        for row in self._personal_records():
            category = _clean_text(row.get("category", "")).lower()
            if category not in {"profile", "family", "pet", "household"}:
                continue
            value = _clean_text(row.get("value", ""))
            field = _clean_text(row.get("field", ""))
            subject = _clean_text(row.get("subject", ""))
            if not value or not field:
                continue
            key = f"{category}:{subject or 'self'}:{field}"
            updated_at = _clean_text(row.get("updated_at", ""))
            source = _clean_text(row.get("source_label", row.get("source_type", "personal_memory")))
            out.append(
                MemoryRecord(
                    category="semantic",
                    key=key,
                    value=value,
                    source=source,
                    source_score=self._source_score(source, updated_at),
                    updated_at=updated_at,
                    confidence=float(row.get("confidence", 0.7) or 0.7),
                    record_id=_clean_text(row.get("id", "")),
                    conflict_key=key,
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
                    source_score=_recency_score(ts),
                    updated_at=ts,
                    confidence=0.65,
                    record_id=_clean_text(msg.get("id", "")),
                    conflict_key=f"episode:{_clean_text(msg.get('id', ''))}",
                )
            )
        return out

    def _episodic_from_personal(self) -> list[MemoryRecord]:
        out: list[MemoryRecord] = []
        for row in self._personal_records():
            field = _clean_text(row.get("field", "")).lower()
            if field not in {"birthday", "important_dates"}:
                continue
            value = _clean_text(row.get("value", ""))
            if not value:
                continue
            subject = _clean_text(row.get("subject", "")) or "user"
            updated_at = _clean_text(row.get("updated_at", ""))
            out.append(
                MemoryRecord(
                    category="episodic",
                    key=f"personal:{subject}:{field}",
                    value=value,
                    source="personal_memory",
                    source_score=_recency_score(updated_at),
                    updated_at=updated_at,
                    confidence=float(row.get("confidence", 0.68) or 0.68),
                    record_id=_clean_text(row.get("id", "")),
                    conflict_key=f"episodic:{subject}:{field}",
                )
            )
        return out

    def _procedural_from_personal(self) -> list[MemoryRecord]:
        out: list[MemoryRecord] = []
        for row in self._personal_records():
            tags = row.get("tags") if isinstance(row.get("tags"), list) else []
            field = _clean_text(row.get("field", "")).lower()
            value = _clean_text(row.get("value", ""))
            if not value:
                continue
            is_procedural = field in {"notes", "work", "routine", "workflow"}
            if not is_procedural and tags:
                joined = " ".join(_clean_text(t).lower() for t in tags)
                is_procedural = any(token in joined for token in {"howto", "process", "routine", "playbook"})
            if not is_procedural:
                continue
            subject = _clean_text(row.get("subject", "")) or "user"
            updated_at = _clean_text(row.get("updated_at", ""))
            out.append(
                MemoryRecord(
                    category="procedural",
                    key=f"procedural:{subject}:{field}",
                    value=value,
                    source="personal_memory",
                    source_score=_recency_score(updated_at),
                    updated_at=updated_at,
                    confidence=float(row.get("confidence", 0.66) or 0.66),
                    record_id=_clean_text(row.get("id", "")),
                    conflict_key=f"procedural:{subject}:{field}",
                )
            )
        return out

    def resolve_semantic_conflicts(self, records: list[MemoryRecord]) -> tuple[list[MemoryRecord], list[dict[str, Any]]]:
        grouped: dict[str, list[MemoryRecord]] = {}
        for row in records:
            key = _clean_text(row.conflict_key) or _clean_text(row.key)
            if not key:
                continue
            grouped.setdefault(key, []).append(row)

        resolved: list[MemoryRecord] = []
        conflicts: list[dict[str, Any]] = []
        for key, rows in grouped.items():
            if len(rows) == 1:
                resolved.append(rows[0])
                continue
            distinct_values = {_clean_text(r.value) for r in rows if _clean_text(r.value)}
            sorted_rows = sorted(
                rows,
                key=lambda r: (float(r.source_score), float(r.confidence), _parse_iso(r.updated_at).timestamp() if _parse_iso(r.updated_at) else 0.0),
                reverse=True,
            )
            winner = sorted_rows[0]
            resolved.append(winner)
            if len(distinct_values) > 1:
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

        semantic_pool: list[MemoryRecord] = []
        episodic_pool: list[MemoryRecord] = []
        procedural_pool: list[MemoryRecord] = []

        if "semantic" in kind_set:
            semantic_pool.extend(self._semantic_from_project(project))
            semantic_pool.extend(self._semantic_from_topics(query_text))
            semantic_pool.extend(self._semantic_from_personal())
        if "episodic" in kind_set:
            episodic_pool.extend(self._episodic_from_personal())
            episodic_pool.extend(self._episodic_from_conversation(query_text, conversation_id=conversation_id))
        if "procedural" in kind_set:
            procedural_pool.extend(self._procedural_from_personal())

        def _rank(rows: list[MemoryRecord]) -> list[MemoryRecord]:
            scored: list[tuple[float, MemoryRecord]] = []
            for row in rows:
                hay = f"{row.key} {row.value} {row.source}"
                score = self._similarity(query_text, hay)
                score += float(row.source_score)
                score += max(0.0, min(0.2, float(row.confidence) * 0.2))
                scored.append((score, row))
            scored.sort(key=lambda item: item[0], reverse=True)
            return [row for score, row in scored if score > 0][: max(4, per_kind * 3)]

        semantic_ranked = _rank(semantic_pool)
        semantic_resolved, conflicts = self.resolve_semantic_conflicts(semantic_ranked)
        semantic_rows = semantic_resolved[:per_kind]
        episodic_rows = _rank(episodic_pool)[:per_kind]
        procedural_rows = _rank(procedural_pool)[:per_kind]

        out_rows: dict[str, list[dict[str, Any]]] = {
            "semantic": [r.to_dict() for r in semantic_rows],
            "episodic": [r.to_dict() for r in episodic_rows],
            "procedural": [r.to_dict() for r in procedural_rows],
        }
        return {
            "query": query_text,
            "k_per_kind": per_kind,
            "results": out_rows,
            "conflicts": conflicts,
        }
