from __future__ import annotations

from typing import Any


class ProjectReadinessAssessor:
    """Simple readiness lens for phase-9 watchtower scanning."""

    def assess(
        self,
        *,
        project_kernel: dict[str, Any],
        pending_cards: list[dict[str, Any]],
    ) -> dict[str, Any]:
        knowledge = project_kernel.get("knowledge_spine", {}) if isinstance(project_kernel.get("knowledge_spine", {}), dict) else {}
        execution = project_kernel.get("execution_spine", {}) if isinstance(project_kernel.get("execution_spine", {}), dict) else {}
        score = 100
        blockers: list[str] = []

        if not str(knowledge.get("domain", "")).strip():
            score -= 25
            blockers.append("missing_domain")
        if not str(knowledge.get("topic", "")).strip():
            score -= 20
            blockers.append("missing_topic")
        if not str(execution.get("make_type", "")).strip():
            score -= 20
            blockers.append("missing_make_type")
        if not str(execution.get("research_focus", "")).strip():
            score -= 15
            blockers.append("missing_research_focus")

        queued = [x for x in pending_cards if str(x.get("status", "")).strip().lower() == "queued"]
        score -= min(30, 5 * len(queued))

        state = "ready"
        if score < 75:
            state = "needs_attention"
        if score < 50:
            state = "blocked"

        return {
            "state": state,
            "score": max(0, min(100, int(score))),
            "blocking_gaps": blockers,
            "queued_card_count": len(queued),
        }
