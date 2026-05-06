from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class PipelineSpec:
    name: str
    input_contract: tuple[str, ...]
    stages: tuple[str, ...]
    final_stage: str

    def as_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "input_contract": list(self.input_contract),
            "stages": list(self.stages),
            "final_stage": self.final_stage,
        }


DEFAULT_PIPELINES: tuple[PipelineSpec, ...] = (
    PipelineSpec(
        name="research_pipeline",
        input_contract=("text", "project_slug", "domain", "pipeline"),
        stages=("intake", "domain_framing", "source_discovery", "evidence_analysis", "nuance_pass", "synthesis", "cag_promotion_gate"),
        final_stage="synthesis",
    ),
    PipelineSpec(
        name="build_pipeline",
        input_contract=("text", "project_slug", "pipeline", "target"),
        stages=("requirements", "architecture", "implementation_plan", "patch_artifact_generation", "verification"),
        final_stage="verification",
    ),
    PipelineSpec(
        name="code_fix_pipeline",
        input_contract=("text", "project_slug", "pipeline"),
        stages=("planner", "code_localizer", "patch_writer", "reviewer", "test_fixer", "finalizer"),
        final_stage="finalizer",
    ),
)

_PIPELINE_BY_NAME = {row.name: row for row in DEFAULT_PIPELINES}


def default_pipeline_specs() -> list[PipelineSpec]:
    return list(DEFAULT_PIPELINES)


def pipeline_spec_for_name(name: str) -> PipelineSpec | None:
    return _PIPELINE_BY_NAME.get(str(name or "").strip())
