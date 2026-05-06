from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from cag.scope import build_scope, scope_to_dict
from shared_tools.phase0 import lane_to_pipeline
from taxonomy.domains import domain_for_topic_type, normalize_domain
from taxonomy.make_types import infer_make_type, normalize_make_type
from taxonomy.research_focus import infer_research_focus, normalize_research_focus

from .schema import ProjectKernel


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _slug(value: str) -> str:
    text = "_".join(str(value or "").strip().lower().split())
    return text or "general"


class ProjectKernelStore:
    def __init__(self, repo_root: Path) -> None:
        self.repo_root = Path(repo_root)
        self.root = self.repo_root / "Runtime" / "project_kernels"
        self.root.mkdir(parents=True, exist_ok=True)

    def _path_for(self, project_id: str) -> Path:
        return self.root / f"{_slug(project_id)}.json"

    def get_or_create(self, project_id: str) -> ProjectKernel:
        key = _slug(project_id)
        path = self._path_for(key)
        if path.exists():
            try:
                payload = json.loads(path.read_text(encoding="utf-8"))
                if isinstance(payload, dict):
                    kernel = ProjectKernel.from_dict(payload)
                    if not kernel.project_id:
                        kernel.project_id = key
                    return kernel
            except Exception:
                pass
        kernel = ProjectKernel(project_id=key)
        kernel.knowledge_spine.project = key
        self.save(kernel)
        return kernel

    def save(self, kernel: ProjectKernel) -> ProjectKernel:
        kernel.updated_at = _now_iso()
        path = self._path_for(kernel.project_id)
        path.write_text(json.dumps(kernel.as_dict(), indent=2, ensure_ascii=True), encoding="utf-8")
        return kernel

    def update_for_turn(
        self,
        *,
        project_id: str,
        lane: str,
        topic_type: str = "general",
        query_text: str = "",
        query_mode: str = "",
        make_type: str = "",
        make_intent: str = "",
        specialist_stages: list[str] | None = None,
    ) -> ProjectKernel:
        kernel = self.get_or_create(project_id)
        pipeline = lane_to_pipeline(lane)
        domain = normalize_domain(domain_for_topic_type(topic_type))
        resolved_make_type = normalize_make_type(make_type) or infer_make_type(text=query_text, target=make_type, lane=lane)
        focus = normalize_research_focus(
            infer_research_focus(
                text=query_text,
                query_mode=query_mode,
                pipeline=pipeline,
                make_type=resolved_make_type,
            )
        )

        kernel.execution_spine.pipeline = pipeline
        kernel.execution_spine.make_type = resolved_make_type or "research_brief"
        kernel.execution_spine.make_intent = str(make_intent or "").strip() or str(query_mode or "").strip() or "general_research"
        kernel.execution_spine.research_focus = focus
        if specialist_stages is not None:
            kernel.execution_spine.specialist_stages = [str(x).strip() for x in specialist_stages if str(x).strip()]

        if pipeline not in kernel.active_pipelines:
            kernel.active_pipelines.append(pipeline)

        kernel.knowledge_spine.domain = domain
        kernel.knowledge_spine.topic = str(topic_type or "general").strip().lower() or "general"
        kernel.knowledge_spine.project = _slug(project_id)
        kernel.knowledge_spine.thread = f"thread_{_slug(project_id)}"
        kernel.knowledge_spine.run = datetime.now(timezone.utc).strftime("run_%Y%m%d_%H%M%S")
        return self.save(kernel)

    def snapshot(self, project_id: str) -> dict[str, Any]:
        kernel = self.get_or_create(project_id)
        payload = kernel.as_dict()
        scope = build_scope(
            level="run",
            domain=kernel.knowledge_spine.domain,
            topic=kernel.knowledge_spine.topic,
            thread=kernel.knowledge_spine.thread,
            project=kernel.knowledge_spine.project,
            run=kernel.knowledge_spine.run,
        )
        payload["current_scope"] = scope_to_dict(scope)
        return payload
