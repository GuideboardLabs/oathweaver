from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from shared_tools.phase0 import lane_to_pipeline


@dataclass(slots=True)
class TurnPlan:
    """A compact, serializable description of how a user turn should be handled."""

    project: str
    text: str
    lane: str = "research"
    pipeline: str = "research_pipeline"
    query_mode: str = "chat"
    complexity: str = "simple"
    domain: str = "general_research"
    make_type: str = "research_brief"
    make_intent: str = "general_research"
    research_focus: str = "domain_focused"
    lane_override: str | None = None
    should_run_foraging: bool = False
    meta: dict[str, Any] = field(default_factory=dict)

    def as_dict(self) -> dict[str, Any]:
        return {
            "project": self.project,
            "text": self.text,
            "lane": self.lane,
            "pipeline": self.pipeline or lane_to_pipeline(self.lane),
            "query_mode": self.query_mode,
            "complexity": self.complexity,
            "domain": self.domain,
            "make_type": self.make_type,
            "make_intent": self.make_intent,
            "research_focus": self.research_focus,
            "lane_override": self.lane_override,
            "should_run_foraging": self.should_run_foraging,
            "meta": dict(self.meta),
        }
