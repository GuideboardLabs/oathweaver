from __future__ import annotations

from pathlib import Path

from .repositories import ProjectPipelineRepository, WatchtowerRepository


def migrate_runtime_state(repo_root: Path) -> dict[str, object]:
    project_repo = ProjectPipelineRepository(repo_root)
    watch_repo = WatchtowerRepository(repo_root)
    return {
        "project_pipeline_rows": len(project_repo.list_all()),
        "watch_rows": len(watch_repo.list_watches()),
        "research_card_rows": len(watch_repo.list_briefings(limit=500)),
    }


def clear_structured_runtime_state(repo_root: Path) -> None:
    ProjectPipelineRepository(repo_root).clear_all()
    WatchtowerRepository(repo_root).clear_all()
