from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from specialists import build_specialist_pack, derive_specialist_role


@dataclass(frozen=True)
class SpecialistManifest:
    stage: str
    specialist_role: str
    role_prompt: str
    output_schema: str
    cag_query_profile: str
    retrieval_evidence_template: str
    few_shot_library: str
    tool_permissions: tuple[str, ...]
    verifier_rubric: str
    optional_adapter: str
    expected_next_role: str
    estimated_tokens: int

    def as_dict(self) -> dict[str, Any]:
        return {
            "stage": self.stage,
            "specialist_role": self.specialist_role,
            "role_prompt": self.role_prompt,
            "output_schema": self.output_schema,
            "cag_query_profile": self.cag_query_profile,
            "retrieval_evidence_template": self.retrieval_evidence_template,
            "few_shot_library": self.few_shot_library,
            "tool_permissions": list(self.tool_permissions),
            "verifier_rubric": self.verifier_rubric,
            "optional_adapter": self.optional_adapter,
            "expected_next_role": self.expected_next_role,
            "estimated_tokens": int(self.estimated_tokens),
        }


class SpecialistRegistry:
    """Manifest registry for deterministic stage specialists."""

    def manifest_for_stage(
        self,
        *,
        stage: str,
        pipeline: str,
        next_stage: str = "",
        domain: str = "general_research",
        make_type: str = "model_runtime_system",
        research_focus: str = "implementation_focused",
    ) -> SpecialistManifest:
        stage_key = str(stage or "").strip()
        role = derive_specialist_role(
            stage=stage_key,
            domain=domain,
            make_type=make_type,
            research_focus=research_focus,
        )
        pack = build_specialist_pack(
            specialist_id=role,
            pipeline_stage=stage_key,
            next_stage=str(next_stage or "").strip(),
            domain=str(domain or "").strip(),
            make_type=str(make_type or "").strip(),
            research_focus=str(research_focus or "").strip(),
        )
        return SpecialistManifest(
            stage=stage_key,
            specialist_role=pack.specialist_id,
            role_prompt=pack.role_prompt,
            output_schema=pack.output_schema,
            cag_query_profile=pack.cag_query_profile if pipeline else pack.cag_query_profile,
            retrieval_evidence_template=pack.retrieval_evidence_template,
            few_shot_library=pack.few_shot_library,
            tool_permissions=tuple(pack.tool_permissions),
            verifier_rubric=pack.verifier_rubric,
            optional_adapter=pack.optional_adapter,
            expected_next_role=derive_specialist_role(
                stage=str(next_stage or "").strip(),
                domain=domain,
                make_type=make_type,
                research_focus=research_focus,
            )
            if str(next_stage or "").strip()
            else "",
            estimated_tokens=int(pack.estimated_tokens),
        )
