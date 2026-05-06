from __future__ import annotations

from pathlib import Path
from typing import Any

from core.capability_registry import CapabilityRegistry

from .knowledge_gap_detector import KnowledgeGapDetector
from .project_readiness import ProjectReadinessAssessor
from .research_cards import ResearchCardStore


class WatchtowerScout:
    """Background scout that emits queued watchtower cards with explicit scope."""

    def __init__(self, repo_root: Path) -> None:
        self.repo_root = Path(repo_root)
        self.card_store = ResearchCardStore(self.repo_root)
        self.detector = KnowledgeGapDetector()
        self.readiness = ProjectReadinessAssessor()
        self.capability_registry = CapabilityRegistry(self.repo_root)

    def queue_research_card_from_briefing(self, *, briefing: dict[str, Any]) -> dict[str, Any]:
        topic = str(briefing.get("topic", "")).strip() or "general"
        title = str(briefing.get("headline", "")).strip() or f"Watchtower research: {topic}"
        summary = str(briefing.get("summary", "")).strip() or str(briefing.get("preview", "")).strip()
        watch_id = str(briefing.get("watch_id", "")).strip()
        return self.card_store.queue_card(
            {
                "card_type": "research_card",
                "scope_level": "topic",
                "scope": {
                    "domain": str(briefing.get("domain", "")).strip(),
                    "topic": topic,
                    "thread": "",
                    "project": "general",
                    "run": "",
                },
                "title": title,
                "summary": summary,
                "recommended_action": "Review this card and decide: accept, reject, queue, or run.",
                "priority": "medium",
                "evidence": [
                    {
                        "kind": "watchtower_briefing",
                        "value": {
                            "watch_id": watch_id,
                            "briefing_id": str(briefing.get("id", "")).strip(),
                        },
                    }
                ],
                "source": "watchtower.research_cards",
                "linked_run_id": "",
            }
        )

    def scan_project(
        self,
        *,
        project: str,
        project_kernel: dict[str, Any],
        auditor_report: dict[str, Any],
    ) -> dict[str, Any]:
        cards = self.detector.detect(
            project=project,
            project_kernel=project_kernel,
            auditor_report=auditor_report,
            capability_claims=self.capability_registry.list_claims(),
        )
        queued: list[dict[str, Any]] = []
        for row in cards:
            queued.append(self.card_store.queue_card(row))

        readiness = self.readiness.assess(
            project_kernel=project_kernel,
            pending_cards=self.card_store.list_cards(limit=200, status="queued"),
        )
        return {
            "project": project,
            "queued_count": len(queued),
            "queued_cards": queued,
            "readiness": readiness,
            "summary": self.card_store.summarize(),
        }
