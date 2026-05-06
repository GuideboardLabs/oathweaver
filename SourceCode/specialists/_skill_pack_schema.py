from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class SpecialistSkillPack:
    specialist_id: str
    display_name: str
    version: str
    pipeline_stage: str
    domain: str
    make_type: str
    research_focus: str
    role_prompt: str
    output_schema: str
    cag_query_profile: str
    retrieval_evidence_template: str
    few_shot_library: str
    tool_permissions: tuple[str, ...]
    verifier_rubric: str
    optional_adapter: str
    next_stage: str
    estimated_tokens: int

    def as_dict(self) -> dict[str, Any]:
        return {
            "specialist_id": self.specialist_id,
            "display_name": self.display_name,
            "version": self.version,
            "pipeline_stage": self.pipeline_stage,
            "domain": self.domain,
            "make_type": self.make_type,
            "research_focus": self.research_focus,
            "role_prompt": self.role_prompt,
            "output_schema": self.output_schema,
            "cag_query_profile": self.cag_query_profile,
            "retrieval_evidence_template": self.retrieval_evidence_template,
            "few_shot_library": self.few_shot_library,
            "tool_permissions": list(self.tool_permissions),
            "verifier_rubric": self.verifier_rubric,
            "optional_adapter": self.optional_adapter,
            "next_stage": self.next_stage,
            "estimated_tokens": int(self.estimated_tokens),
        }


REQUIRED_PACK_FIELDS: tuple[str, ...] = (
    "role_prompt",
    "output_schema",
    "cag_query_profile",
    "retrieval_evidence_template",
    "few_shot_library",
    "tool_permissions",
    "verifier_rubric",
    "optional_adapter",
    "next_stage",
)


def validate_skill_pack(pack: SpecialistSkillPack) -> list[str]:
    errors: list[str] = []
    row = pack.as_dict()
    for key in REQUIRED_PACK_FIELDS:
        value = row.get(key)
        if key == "optional_adapter":
            if value is None:
                errors.append(f"missing:{key}")
            continue
        if key == "tool_permissions":
            if not isinstance(value, list) or not value:
                errors.append(f"invalid:{key}")
            continue
        if isinstance(value, str):
            if not value.strip() and key != "next_stage":
                errors.append(f"missing:{key}")
            continue
        if value is None:
            errors.append(f"missing:{key}")
    if not str(pack.specialist_id or "").strip():
        errors.append("missing:specialist_id")
    if int(pack.estimated_tokens) <= 0:
        errors.append("invalid:estimated_tokens")
    return errors
