from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class TopicPolicy:
    topic_type: str
    default_roles: tuple[str, ...]
    optional_roles: tuple[str, ...]
    disallowed_by_default: tuple[str, ...]
    confidence_cap: float | None
    preferred_source_tiers: tuple[str, ...]


TOPIC_POLICIES: dict[str, TopicPolicy] = {
    "_default": TopicPolicy(
        topic_type="_default",
        default_roles=("context_and_background_researcher", "critical_analyst", "implications_researcher"),
        optional_roles=("quantitative_evidence_analyst",),
        disallowed_by_default=("legal_compliance_researcher",),
        confidence_cap=None,
        preferred_source_tiers=("tier1", "tier2"),
    ),
    "general": TopicPolicy(
        topic_type="general",
        default_roles=("context_and_background_researcher", "critical_analyst", "implications_researcher"),
        optional_roles=("quantitative_evidence_analyst",),
        disallowed_by_default=("legal_compliance_researcher",),
        confidence_cap=None,
        preferred_source_tiers=("tier1", "tier2"),
    ),
    "technical": TopicPolicy(
        topic_type="technical",
        default_roles=("technical_feasibility_researcher", "critical_analyst", "project_translator"),
        optional_roles=("comparative_market_researcher", "quantitative_evidence_analyst"),
        disallowed_by_default=(),
        confidence_cap=None,
        preferred_source_tiers=("tier1", "tier2"),
    ),
    "medical": TopicPolicy(
        topic_type="medical",
        default_roles=("clinical_evidence_researcher", "guideline_verifier", "safety_risk_researcher", "critical_analyst"),
        optional_roles=("quantitative_evidence_analyst", "legal_compliance_researcher"),
        disallowed_by_default=(),
        confidence_cap=0.85,
        preferred_source_tiers=("tier1", "tier2"),
    ),
    "finance": TopicPolicy(
        topic_type="finance",
        default_roles=("comparative_market_researcher", "critical_analyst", "implications_researcher"),
        optional_roles=("quantitative_evidence_analyst", "legal_compliance_researcher"),
        disallowed_by_default=(),
        confidence_cap=None,
        preferred_source_tiers=("tier1", "tier2"),
    ),
    "science": TopicPolicy(
        topic_type="science",
        default_roles=("context_and_background_researcher", "critical_analyst", "quantitative_evidence_analyst"),
        optional_roles=(),
        disallowed_by_default=(),
        confidence_cap=None,
        preferred_source_tiers=("tier1", "tier2"),
    ),
    "history": TopicPolicy(
        topic_type="history",
        default_roles=("context_and_background_researcher", "critical_analyst", "implications_researcher"),
        optional_roles=(),
        disallowed_by_default=(),
        confidence_cap=None,
        preferred_source_tiers=("tier1", "tier2", "tier3"),
    ),
    "law": TopicPolicy(
        topic_type="law",
        default_roles=("legal_compliance_researcher", "critical_analyst", "implications_researcher"),
        optional_roles=(),
        disallowed_by_default=(),
        confidence_cap=0.8,
        preferred_source_tiers=("tier1", "tier2"),
    ),
}


PROJECT_TYPE_ROLE_HINTS: dict[str, tuple[str, ...]] = {
    "web_app": ("technical_feasibility_researcher", "project_translator"),
    "backend_service": ("technical_feasibility_researcher", "project_translator"),
    "desktop_app": ("technical_feasibility_researcher", "project_translator"),
    "library_sdk": ("technical_feasibility_researcher", "project_translator"),
    "developer_tool": ("technical_feasibility_researcher", "project_translator"),
    "benchmark_suite": ("benchmark_designer", "critical_analyst"),
    "model_runtime_system": ("runtime_architect", "memory_systems_analyst", "systems_skeptic"),
}


RESEARCH_FOCUS_ROLE_HINTS: dict[str, tuple[str, ...]] = {
    "domain_focused": ("context_and_background_researcher",),
    "product_focused": ("comparative_market_researcher", "project_translator"),
    "implementation_focused": ("technical_feasibility_researcher", "project_translator"),
    "evidence_focused": ("evidence_adjudicator", "critical_analyst"),
    "benchmark_focused": ("benchmark_designer", "quantitative_evidence_analyst"),
    "risk_focused": ("safety_risk_researcher", "critical_analyst"),
}


def topic_policy_for(topic_type: str) -> TopicPolicy:
    key = str(topic_type or "").strip().lower() or "_default"
    return TOPIC_POLICIES.get(key) or TOPIC_POLICIES["_default"]


def stage_roles_for(
    *,
    topic_type: str,
    make_type: str = "",
    research_focus: str = "",
    pipeline_stage: str = "",
) -> tuple[str, ...]:
    policy = topic_policy_for(topic_type)
    out: list[str] = list(policy.default_roles)
    out.extend(PROJECT_TYPE_ROLE_HINTS.get(str(make_type or "").strip().lower(), ()))
    out.extend(RESEARCH_FOCUS_ROLE_HINTS.get(str(research_focus or "").strip().lower(), ()))

    stage = str(pipeline_stage or "").strip().lower()
    if stage == "skeptic":
        out.append("contrarian_red_team")
    elif stage == "synthesis":
        out.append("evidence_adjudicator")

    # keep order, remove duplicates, apply disallow list
    cleaned: list[str] = []
    disallowed = set(policy.disallowed_by_default)
    for role in out:
        r = str(role or "").strip()
        if not r or r in disallowed or r in cleaned:
            continue
        cleaned.append(r)
    return tuple(cleaned)


__all__ = [
    "PROJECT_TYPE_ROLE_HINTS",
    "RESEARCH_FOCUS_ROLE_HINTS",
    "TOPIC_POLICIES",
    "TopicPolicy",
    "stage_roles_for",
    "topic_policy_for",
]

