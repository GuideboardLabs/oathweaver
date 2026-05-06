from __future__ import annotations

from typing import Callable

from ._skill_pack_schema import SpecialistSkillPack, validate_skill_pack
from .auditor import build_pack as build_auditor_pack
from .memory_critic import build_pack as build_memory_critic_pack
from .planner import build_pack as build_planner_pack
from .researcher import build_pack as build_researcher_pack
from .skeptic import build_pack as build_skeptic_pack
from .synthesizer import build_pack as build_synthesizer_pack
from .verifier import build_pack as build_verifier_pack


Builder = Callable[..., SpecialistSkillPack]


_BUILDERS: dict[str, Builder] = {
    "planner": build_planner_pack,
    "researcher": build_researcher_pack,
    "skeptic": build_skeptic_pack,
    "synthesizer": build_synthesizer_pack,
    "verifier": build_verifier_pack,
    "memory_critic": build_memory_critic_pack,
    "auditor": build_auditor_pack,
}

_ALIASES: dict[str, str] = {
    "runtime_architect": "planner",
    "memory_systems_analyst": "memory_critic",
    "benchmark_designer": "auditor",
    "code_reviewer": "verifier",
    "systems_skeptic": "skeptic",
}


def specialist_roster() -> list[str]:
    return list(_BUILDERS.keys())


def derive_specialist_role(
    *,
    stage: str,
    domain: str,
    make_type: str,
    research_focus: str,
) -> str:
    stage_key = str(stage or "").strip().lower()
    domain_key = str(domain or "").strip().lower().replace(" ", "_")
    make_key = str(make_type or "").strip().lower().replace(" ", "_").replace("/", "_")
    focus_key = str(research_focus or "").strip().lower().replace(" ", "_")

    # Intersection-derived overrides for runtime-system work.
    if domain_key in {"computer_science", "programming", "computer_science_programming", "general_research"}:
        if make_key in {"model_runtime_system", "modelruntime_system", "runtime_system", "model_runtime", "model_runtime_system"}:
            if focus_key in {"implementation_focused", "implementation-focused"}:
                if stage_key in {"architecture", "requirements", "implementation_plan"}:
                    return "runtime_architect"
                if stage_key in {"evidence_analysis", "verification"}:
                    return "benchmark_designer"
                if stage_key in {"patch_writer", "patch_artifact_generation", "reviewer"}:
                    return "code_reviewer"
                if stage_key in {"nuance_pass", "reviewer"}:
                    return "systems_skeptic"
                if stage_key in {"cag_promotion_gate"}:
                    return "memory_systems_analyst"

    stage_map = {
        "intake": "planner",
        "domain_framing": "researcher",
        "source_discovery": "researcher",
        "evidence_analysis": "auditor",
        "nuance_pass": "skeptic",
        "synthesis": "synthesizer",
        "cag_promotion_gate": "memory_critic",
        "requirements": "planner",
        "architecture": "planner",
        "implementation_plan": "planner",
        "patch_artifact_generation": "planner",
        "verification": "verifier",
        "planner": "planner",
        "code_localizer": "researcher",
        "patch_writer": "planner",
        "reviewer": "skeptic",
        "test_fixer": "verifier",
        "finalizer": "synthesizer",
    }
    return stage_map.get(stage_key, "planner")


def build_specialist_pack(
    *,
    specialist_id: str,
    pipeline_stage: str,
    next_stage: str,
    domain: str,
    make_type: str,
    research_focus: str,
) -> SpecialistSkillPack:
    key = str(specialist_id or "").strip().lower()
    base_key = _ALIASES.get(key, key)
    builder = _BUILDERS.get(base_key)
    if builder is None:
        builder = build_planner_pack
    pack = builder(
        pipeline_stage=str(pipeline_stage or "").strip(),
        next_stage=str(next_stage or "").strip(),
        domain=str(domain or "").strip(),
        make_type=str(make_type or "").strip(),
        research_focus=str(research_focus or "").strip(),
    )
    if key and key != pack.specialist_id:
        pack = SpecialistSkillPack(
            specialist_id=key,
            display_name=key.replace("_", " ").title(),
            version=pack.version,
            pipeline_stage=pack.pipeline_stage,
            domain=pack.domain,
            make_type=pack.make_type,
            research_focus=pack.research_focus,
            role_prompt=pack.role_prompt,
            output_schema=pack.output_schema,
            cag_query_profile=pack.cag_query_profile,
            retrieval_evidence_template=pack.retrieval_evidence_template,
            few_shot_library=pack.few_shot_library,
            tool_permissions=tuple(pack.tool_permissions),
            verifier_rubric=pack.verifier_rubric,
            optional_adapter=pack.optional_adapter,
            next_stage=pack.next_stage,
            estimated_tokens=pack.estimated_tokens,
        )
    errors = validate_skill_pack(pack)
    if errors:
        raise ValueError(f"Invalid specialist skill pack for '{key}': {', '.join(errors)}")
    return pack


__all__ = [
    "SpecialistSkillPack",
    "build_specialist_pack",
    "derive_specialist_role",
    "specialist_roster",
    "validate_skill_pack",
]
