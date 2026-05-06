from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass
class ContextPack:
    context_pack_id: str
    run_id: str
    pipeline: str
    stage: str
    specialist_role: str
    project: str
    domain: str
    topic: str
    thread: str
    token_budget: int
    output_contract: str
    included_memory: list[str] = field(default_factory=list)
    excluded_memory_reasoning: list[str] = field(default_factory=list)
    memory_snippets: list[dict[str, Any]] = field(default_factory=list)
    retrieval_results: dict[str, Any] = field(default_factory=dict)
    benchmark_lessons: list[str] = field(default_factory=list)
    few_shot_examples: list[dict[str, str]] = field(default_factory=list)
    created_at: str = field(default_factory=_now_iso)

    def as_dict(self) -> dict[str, Any]:
        return {
            "context_pack_id": self.context_pack_id,
            "run_id": self.run_id,
            "pipeline": self.pipeline,
            "stage": self.stage,
            "specialist_role": self.specialist_role,
            "project": self.project,
            "domain": self.domain,
            "topic": self.topic,
            "thread": self.thread,
            "token_budget": int(self.token_budget),
            "output_contract": self.output_contract,
            "included_memory": list(self.included_memory),
            "excluded_memory_reasoning": list(self.excluded_memory_reasoning),
            "memory_snippets": [dict(x) for x in self.memory_snippets],
            "retrieval_results": dict(self.retrieval_results),
            "benchmark_lessons": list(self.benchmark_lessons),
            "few_shot_examples": [dict(x) for x in self.few_shot_examples],
            "created_at": self.created_at,
        }


def build_context_pack(payload: dict[str, Any]) -> ContextPack:
    row = dict(payload or {})
    return ContextPack(
        context_pack_id=str(row.get("context_pack_id", "")).strip(),
        run_id=str(row.get("run_id", "")).strip(),
        pipeline=str(row.get("pipeline", "")).strip(),
        stage=str(row.get("stage", "")).strip(),
        specialist_role=str(row.get("specialist_role", "")).strip() or str(row.get("stage", "")).strip(),
        project=str(row.get("project", "")).strip(),
        domain=str(row.get("domain", "")).strip(),
        topic=str(row.get("topic", "")).strip(),
        thread=str(row.get("thread", "")).strip(),
        token_budget=max(0, int(row.get("token_budget", 0) or 0)),
        output_contract=str(row.get("output_contract", "")).strip(),
        included_memory=[str(x).strip() for x in row.get("included_memory", []) if str(x).strip()],
        excluded_memory_reasoning=[str(x).strip() for x in row.get("excluded_memory_reasoning", []) if str(x).strip()],
        memory_snippets=[dict(x) for x in row.get("memory_snippets", []) if isinstance(x, dict)],
        retrieval_results=dict(row.get("retrieval_results", {})) if isinstance(row.get("retrieval_results", {}), dict) else {},
        benchmark_lessons=[str(x).strip() for x in row.get("benchmark_lessons", []) if str(x).strip()],
        few_shot_examples=[dict(x) for x in row.get("few_shot_examples", []) if isinstance(x, dict)],
        created_at=str(row.get("created_at", _now_iso())).strip() or _now_iso(),
    )
