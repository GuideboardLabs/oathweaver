from __future__ import annotations

from specialists._skill_pack_schema import SpecialistSkillPack


def build_pack(*, pipeline_stage: str, next_stage: str, domain: str, make_type: str, research_focus: str) -> SpecialistSkillPack:
    return SpecialistSkillPack(
        specialist_id="memory_critic",
        display_name="Memory Critic",
        version="v1",
        pipeline_stage=pipeline_stage,
        domain=domain,
        make_type=make_type,
        research_focus=research_focus,
        role_prompt="Decide what memory to include, exclude, promote, supersede, or deprecate using strict validation and scope discipline.",
        output_schema=f"{pipeline_stage or 'stage'}_memory_gate_v1",
        cag_query_profile="memory:promotion_scope_contradictions",
        retrieval_evidence_template="memory_critic_evidence_template_v1",
        few_shot_library="memory_critic_few_shots_v1",
        tool_permissions=("workspace_read",),
        verifier_rubric="memory_quality_and_scope_fit_v1",
        optional_adapter="adapter_memory_critic_small",
        next_stage=next_stage,
        estimated_tokens=1450,
    )
