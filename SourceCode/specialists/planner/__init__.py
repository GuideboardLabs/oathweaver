from __future__ import annotations

from specialists._skill_pack_schema import SpecialistSkillPack


def build_pack(*, pipeline_stage: str, next_stage: str, domain: str, make_type: str, research_focus: str) -> SpecialistSkillPack:
    return SpecialistSkillPack(
        specialist_id="planner",
        display_name="Planner",
        version="v1",
        pipeline_stage=pipeline_stage,
        domain=domain,
        make_type=make_type,
        research_focus=research_focus,
        role_prompt="Turn the request into deterministic, ordered implementation steps with explicit constraints.",
        output_schema=f"{pipeline_stage or 'stage'}_plan_v1",
        cag_query_profile="planning:constraints_decisions",
        retrieval_evidence_template="planning_evidence_template_v1",
        few_shot_library="planner_few_shots_v1",
        tool_permissions=("workspace_read", "workspace_write"),
        verifier_rubric="plan_specificity_and_feasibility_v1",
        optional_adapter="",
        next_stage=next_stage,
        estimated_tokens=1400,
    )
