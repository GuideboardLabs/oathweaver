from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from infra.persistence.repositories import ProjectPipelineRepository
from shared_tools.topic_engine import VALID_TOPIC_TYPES

VALID_MODES = {"discovery", "make"}
VALID_TARGETS = {
    "auto", "essay", "brief", "app",
    "product", "gap_analysis", "novel", "report", "tool",
    "dashboard", "blog", "social_post", "landing_page", "api",
}


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _normalize_project_slug(raw: str | None) -> str:
    text = "_".join(str(raw or "").strip().split()).lower()
    return text or "general"


def _normalize_mode(raw: str | None) -> str:
    value = str(raw or "").strip().lower()
    aliases = {
        "research": "discovery", "extend": "discovery", "extend_oathweaver": "discovery",
        "foraging": "discovery", "plan": "discovery", "build": "make",
        "build_make": "make", "build/make": "make",
    }
    value = aliases.get(value, value)
    return value if value in VALID_MODES else "discovery"


def _normalize_target(raw: str | None) -> str:
    value = str(raw or "").strip().lower()
    aliases = {
        "standalone_app": "app", "web_app": "app", "app": "app", "module": "app",
        "widget": "app", "standalone": "app", "script": "tool", "game_design_doc": "report",
        "gdd": "report", "document": "report", "memoir": "novel", "book": "novel",
        "book_draft": "novel", "email": "brief", "general": "auto", "gen": "auto",
        "medical": "auto", "med": "auto", "health": "auto", "animal_care": "auto",
        "pet_care": "auto", "veterinary": "auto", "finance": "auto",
        "financial": "auto", "fin": "auto", "sports": "auto", "sport": "auto",
        "history": "auto", "historical": "auto",
        "dashboard": "dashboard", "blog": "blog", "blog_post": "blog",
        "social_post": "social_post", "social_media": "social_post", "social": "social_post",
        "landing_page": "landing_page", "landing": "landing_page",
        "api": "api", "rest_api": "api", "api_service": "api",
    }
    value = aliases.get(value, value)
    return value if value in VALID_TARGETS else "auto"


def _normalize_topic_type(raw: str | None) -> str:
    value = str(raw or "").strip().lower()
    return value if value in VALID_TOPIC_TYPES else "general"


class ProjectPipelineStore:
    def __init__(self, repo_root: Path) -> None:
        self.repo_root = Path(repo_root)
        self.path = self.repo_root / "Runtime" / "project_pipeline.json"
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.repo = ProjectPipelineRepository(self.repo_root)

    def get(self, project: str | None) -> dict[str, Any]:
        return self.repo.get(project)

    def set(
        self,
        project: str | None,
        *,
        mode: str | None = None,
        target: str | None = None,
        topic_type: str | None = None,
    ) -> dict[str, Any]:
        return self.repo.set(project, mode=mode, target=target, topic_type=topic_type)

    def list_all(self) -> dict[str, dict[str, Any]]:
        return self.repo.list_all()
