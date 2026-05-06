from __future__ import annotations

from specialists._skill_pack_schema import SpecialistSkillPack


def build_pack(*, pipeline_stage: str, next_stage: str, domain: str, make_type: str, research_focus: str) -> SpecialistSkillPack:
    return SpecialistSkillPack(
        specialist_id="skeptic",
        display_name="Skeptic",
        version="v1",
        pipeline_stage=pipeline_stage,
        domain=domain,
        make_type=make_type,
        research_focus=research_focus,
        role_prompt="Stress-test assumptions, surface contradictions, and propose precise repairs without rewriting the final answer.",
        output_schema=f"{pipeline_stage or 'stage'}_skeptic_report_v1",
        cag_query_profile="skeptic:contradictions_risks",
        retrieval_evidence_template="skeptic_evidence_template_v1",
        few_shot_library="skeptic_few_shots_v1",
        tool_permissions=("workspace_read",),
        verifier_rubric="risk_identification_and_repair_quality_v1",
        optional_adapter="adapter_skeptic_small",
        next_stage=next_stage,
        estimated_tokens=1350,
    )
