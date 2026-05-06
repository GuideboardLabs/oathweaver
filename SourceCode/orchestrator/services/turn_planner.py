from __future__ import annotations

from pathlib import Path
from typing import Any

from .policy import RoutingPolicy
from .turn_plan import TurnPlan


class TurnPlanner:
    """Centralizes lightweight per-turn planning decisions."""

    def __init__(self, repo_root: Path, policy: RoutingPolicy | None = None) -> None:
        self.repo_root = repo_root
        self.policy = policy or RoutingPolicy(repo_root)

    def plan(
        self,
        text: str,
        *,
        project: str,
        topic_type: str = "general",
        client: Any | None = None,
        model_cfg: dict[str, Any] | None = None,
        current_lane: str = "research",
        recent_context: str = "",
    ) -> TurnPlan:
        normalized = (text or "").strip()
        decision = self.policy.decide(
            normalized,
            project_slug=project,
            topic_type=topic_type,
            client=client,
            model_cfg=model_cfg,
            current_lane=current_lane,
            recent_context=recent_context,
        )
        return TurnPlan(
            project=project,
            text=normalized,
            lane=decision.lane,
            pipeline=decision.pipeline,
            query_mode=decision.query_mode,
            complexity=decision.complexity,
            domain=decision.domain,
            make_type=decision.make_type,
            make_intent=decision.make_intent,
            research_focus=decision.research_focus,
            lane_override=decision.lane_override,
            should_run_foraging=decision.should_run_foraging,
            meta=dict(decision.meta),
        )
