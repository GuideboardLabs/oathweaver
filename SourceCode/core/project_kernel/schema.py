from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass
class KnowledgeSpine:
    domain: str = "general_research"
    topic: str = "general"
    thread: str = "default"
    project: str = "general"
    run: str = ""

    def as_dict(self) -> dict[str, str]:
        return {
            "domain": self.domain,
            "topic": self.topic,
            "thread": self.thread,
            "project": self.project,
            "run": self.run,
        }


@dataclass
class ExecutionSpine:
    make_type: str = "research_brief"
    make_intent: str = "general_research"
    research_focus: str = "domain_focused"
    pipeline: str = "research_pipeline"
    specialist_stages: list[str] = field(default_factory=list)

    def as_dict(self) -> dict[str, Any]:
        return {
            "make_type": self.make_type,
            "make_intent": self.make_intent,
            "research_focus": self.research_focus,
            "pipeline": self.pipeline,
            "specialist_stages": list(self.specialist_stages),
        }


@dataclass
class ModelStack:
    main: str = ""
    embedding: str = ""
    judge: str = ""

    def as_dict(self) -> dict[str, str]:
        return {
            "main": self.main,
            "embedding": self.embedding,
            "judge": self.judge,
        }


@dataclass
class ProjectKernel:
    project_id: str
    mission: str = ""
    constraints: list[str] = field(default_factory=lambda: [
        "local-only",
        "consumer hardware",
        "no cloud APIs",
        "CAG-native memory",
    ])
    active_pipelines: list[str] = field(default_factory=list)
    canonical_model_stack: ModelStack = field(default_factory=ModelStack)
    knowledge_spine: KnowledgeSpine = field(default_factory=KnowledgeSpine)
    execution_spine: ExecutionSpine = field(default_factory=ExecutionSpine)
    updated_at: str = field(default_factory=_now_iso)

    def as_dict(self) -> dict[str, Any]:
        return {
            "project_id": self.project_id,
            "mission": self.mission,
            "constraints": list(self.constraints),
            "active_pipelines": list(self.active_pipelines),
            "canonical_model_stack": self.canonical_model_stack.as_dict(),
            "knowledge_spine": self.knowledge_spine.as_dict(),
            "execution_spine": self.execution_spine.as_dict(),
            "updated_at": self.updated_at,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "ProjectKernel":
        payload = dict(data or {})
        model_row = payload.get("canonical_model_stack", {}) if isinstance(payload.get("canonical_model_stack", {}), dict) else {}
        knowledge = payload.get("knowledge_spine", {}) if isinstance(payload.get("knowledge_spine", {}), dict) else {}
        execution = payload.get("execution_spine", {}) if isinstance(payload.get("execution_spine", {}), dict) else {}
        return cls(
            project_id=str(payload.get("project_id", "general")).strip() or "general",
            mission=str(payload.get("mission", "")).strip(),
            constraints=[str(x).strip() for x in (payload.get("constraints") or []) if str(x).strip()],
            active_pipelines=[str(x).strip() for x in (payload.get("active_pipelines") or []) if str(x).strip()],
            canonical_model_stack=ModelStack(
                main=str(model_row.get("main", "")).strip(),
                embedding=str(model_row.get("embedding", "")).strip(),
                judge=str(model_row.get("judge", "")).strip(),
            ),
            knowledge_spine=KnowledgeSpine(
                domain=str(knowledge.get("domain", "general_research")).strip() or "general_research",
                topic=str(knowledge.get("topic", "general")).strip() or "general",
                thread=str(knowledge.get("thread", "default")).strip() or "default",
                project=str(knowledge.get("project", "general")).strip() or "general",
                run=str(knowledge.get("run", "")).strip(),
            ),
            execution_spine=ExecutionSpine(
                make_type=str(execution.get("make_type", "research_brief")).strip() or "research_brief",
                make_intent=str(execution.get("make_intent", "general_research")).strip() or "general_research",
                research_focus=str(execution.get("research_focus", "domain_focused")).strip() or "domain_focused",
                pipeline=str(execution.get("pipeline", "research_pipeline")).strip() or "research_pipeline",
                specialist_stages=[str(x).strip() for x in (execution.get("specialist_stages") or []) if str(x).strip()],
            ),
            updated_at=str(payload.get("updated_at", "")).strip() or _now_iso(),
        )

