from __future__ import annotations

from specialists._skill_pack_schema import SpecialistSkillPack


def build_pack(*, pipeline_stage: str, next_stage: str, domain: str, make_type: str, research_focus: str) -> SpecialistSkillPack:
    return SpecialistSkillPack(
        specialist_id="synthesizer",
        display_name="Synthesizer",
        version="v1",
        pipeline_stage=pipeline_stage,
        domain=domain,
        make_type=make_type,
        research_focus=research_focus,
        role_prompt="Combine validated evidence into a coherent output that satisfies the stage contract and preserves uncertainty notes.",
        output_schema=f"{pipeline_stage or 'stage'}_synthesis_v1",
        cag_query_profile="synthesis:decisions_constraints_lessons",
        retrieval_evidence_template="synthesizer_evidence_template_v1",
        few_shot_library="synthesizer_few_shots_v1",
        tool_permissions=("workspace_read",),
        verifier_rubric="coherence_contract_compliance_v1",
        optional_adapter="",
        next_stage=next_stage,
        estimated_tokens=1700,
    )
