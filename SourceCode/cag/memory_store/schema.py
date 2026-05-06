from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

from cag.lifecycle import normalize_human_status, normalize_status
from cag.scope import normalize_scope_level


MEMORY_TYPES: tuple[str, ...] = (
    "decision",
    "fact",
    "constraint",
    "lesson",
    "benchmark_implication",
)


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass
class MemoryRow:
    memory_id: str
    text: str
    scope: str
    scope_level: str
    domain: str
    topic: str
    thread: str
    project: str
    run: str
    type: str
    status: str
    evidence: list[dict[str, Any]]
    supersedes: list[str]
    superseded_by: list[str]
    confidence: float
    human_status: str
    tags: list[str]
    promoted_terms: list[str]
    source: str
    created_at: str
    updated_at: str
    expires_at: str
    validation: dict[str, Any]
    contradictions: list[dict[str, Any]]

    @property
    def memory_type(self) -> str:
        return self.type

    def as_dict(self) -> dict[str, Any]:
        return {
            "memory_id": self.memory_id,
            "text": self.text,
            "scope": self.scope,
            "scope_level": self.scope_level,
            "domain": self.domain,
            "topic": self.topic,
            "thread": self.thread,
            "project": self.project,
            "run": self.run,
            "type": self.type,
            "memory_type": self.type,
            "status": self.status,
            "evidence": list(self.evidence),
            "supersedes": list(self.supersedes),
            "superseded_by": list(self.superseded_by),
            "confidence": float(self.confidence),
            "human_status": self.human_status,
            "tags": list(self.tags),
            "promoted_terms": list(self.promoted_terms),
            "source": self.source,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "expires_at": self.expires_at,
            "validation": dict(self.validation),
            "contradictions": list(self.contradictions),
        }


def _clean_list(values: Any) -> list[str]:
    out: list[str] = []
    for value in values or []:
        token = str(value or "").strip()
        if token and token not in out:
            out.append(token)
    return out


def _clean_tags(values: Any) -> list[str]:
    out: list[str] = []
    for value in values or []:
        token = str(value or "").strip().lower()
        if token and token not in out:
            out.append(token)
    return out


def _clean_evidence(values: Any) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for row in values or []:
        if isinstance(row, dict):
            out.append({str(k): v for k, v in row.items()})
    return out


def normalize_memory_type(value: str) -> str:
    key = str(value or "").strip().lower().replace(" ", "_")
    alias = {
        "benchmark": "benchmark_implication",
        "benchmark_implications": "benchmark_implication",
        "benchmark-derived": "benchmark_implication",
        "implication": "benchmark_implication",
    }
    key = alias.get(key, key)
    if key in MEMORY_TYPES:
        return key
    return "decision"


def build_memory_row(payload: dict[str, Any], *, memory_id: str, now_iso: str | None = None) -> MemoryRow:
    now = now_iso or _now_iso()
    scope_level = normalize_scope_level(str(payload.get("scope_level", "project")))
    row = MemoryRow(
        memory_id=str(memory_id),
        text=str(payload.get("text", "")).strip(),
        scope=str(payload.get("scope", "")).strip(),
        scope_level=scope_level,
        domain=str(payload.get("domain", "")).strip(),
        topic=str(payload.get("topic", "")).strip(),
        thread=str(payload.get("thread", "")).strip(),
        project=str(payload.get("project", "")).strip(),
        run=str(payload.get("run", "")).strip(),
        type=normalize_memory_type(str(payload.get("type", payload.get("memory_type", "decision")))),
        status=normalize_status(str(payload.get("status", "candidate"))),
        evidence=_clean_evidence(payload.get("evidence", [])),
        supersedes=_clean_list(payload.get("supersedes", [])),
        superseded_by=_clean_list(payload.get("superseded_by", [])),
        confidence=float(payload.get("confidence", 0.0) or 0.0),
        human_status=normalize_human_status(str(payload.get("human_status", "unreviewed"))),
        tags=_clean_tags(payload.get("tags", [])),
        promoted_terms=_clean_tags(payload.get("promoted_terms", [])),
        source=str(payload.get("source", "promotion_gate")).strip() or "promotion_gate",
        created_at=str(payload.get("created_at", now)).strip() or now,
        updated_at=str(payload.get("updated_at", now)).strip() or now,
        expires_at=str(payload.get("expires_at", "")).strip(),
        validation=dict(payload.get("validation", {})) if isinstance(payload.get("validation", {}), dict) else {},
        contradictions=[dict(x) for x in payload.get("contradictions", []) if isinstance(x, dict)],
    )
    return row
