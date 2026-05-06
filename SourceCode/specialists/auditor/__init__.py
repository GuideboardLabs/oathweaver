from __future__ import annotations

from specialists._skill_pack_schema import SpecialistSkillPack


def build_pack(*, pipeline_stage: str, next_stage: str, domain: str, make_type: str, research_focus: str) -> SpecialistSkillPack:
    return SpecialistSkillPack(
        specialist_id="auditor",
        display_name="Auditor",
        version="v1",
        pipeline_stage=pipeline_stage,
        domain=domain,
        make_type=make_type,
        research_focus=research_focus,
        role_prompt="Audit evidence quality, benchmark implications, and contract compliance; return typed findings.",
        output_schema=f"{pipeline_stage or 'stage'}_audit_v1",
        cag_query_profile="audit:evidence_benchmark_implications",
        retrieval_evidence_template="auditor_evidence_template_v1",
        few_shot_library="auditor_few_shots_v1",
        tool_permissions=("workspace_read", "web"),
        verifier_rubric="audit_findings_quality_v1",
        optional_adapter="adapter_auditor_small",
        next_stage=next_stage,
        estimated_tokens=1550,
    )
