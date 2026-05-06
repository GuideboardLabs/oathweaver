from __future__ import annotations

from specialists._skill_pack_schema import SpecialistSkillPack


def build_pack(*, pipeline_stage: str, next_stage: str, domain: str, make_type: str, research_focus: str) -> SpecialistSkillPack:
    return SpecialistSkillPack(
        specialist_id="researcher",
        display_name="Researcher",
        version="v1",
        pipeline_stage=pipeline_stage,
        domain=domain,
        make_type=make_type,
        research_focus=research_focus,
        role_prompt="Collect primary evidence and extract high-signal facts relevant to the current stage.",
        output_schema=f"{pipeline_stage or 'stage'}_research_v1",
        cag_query_profile="research:evidence_first",
        retrieval_evidence_template="research_evidence_template_v1",
        few_shot_library="researcher_few_shots_v1",
        tool_permissions=("workspace_read", "web"),
        verifier_rubric="source_quality_and_relevance_v1",
        optional_adapter="",
        next_stage=next_stage,
        estimated_tokens=1650,
    )
