from __future__ import annotations

from specialists._skill_pack_schema import SpecialistSkillPack


def build_pack(*, pipeline_stage: str, next_stage: str, domain: str, make_type: str, research_focus: str) -> SpecialistSkillPack:
    return SpecialistSkillPack(
        specialist_id="verifier",
        display_name="Verifier",
        version="v1",
        pipeline_stage=pipeline_stage,
        domain=domain,
        make_type=make_type,
        research_focus=research_focus,
        role_prompt="Verify claims against available evidence, tests, and constraints; emit explicit pass/fail checks.",
        output_schema=f"{pipeline_stage or 'stage'}_verification_v1",
        cag_query_profile="verification:benchmarks_tests_constraints",
        retrieval_evidence_template="verifier_evidence_template_v1",
        few_shot_library="verifier_few_shots_v1",
        tool_permissions=("workspace_read", "tests"),
        verifier_rubric="verification_coverage_v1",
        optional_adapter="adapter_verifier_small",
        next_stage=next_stage,
        estimated_tokens=1300,
    )
