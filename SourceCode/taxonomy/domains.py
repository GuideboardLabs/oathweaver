from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class DomainSpec:
    key: str
    label: str
    description: str
    serious_default: bool = True


DOMAINS: tuple[DomainSpec, ...] = (
    DomainSpec("computer_science_programming", "Computer Science / Programming", "Software engineering, systems, and runtime architecture."),
    DomainSpec("mathematics", "Mathematics", "Math theory, applied math, and quantitative reasoning."),
    DomainSpec("science", "Science", "Natural and applied sciences."),
    DomainSpec("history", "History", "Historical analysis and historical sources."),
    DomainSpec("writing_rhetoric", "Writing / Rhetoric", "Technical and persuasive writing craft."),
    DomainSpec("business_strategy", "Business / Strategy", "Business analysis, strategy, and planning."),
    DomainSpec("law_policy", "Law / Policy", "Legal and policy research."),
    DomainSpec("engineering", "Engineering", "Applied engineering disciplines."),
    DomainSpec("creative", "Creative", "Fiction, worldbuilding, scripts, and narrative work."),
    DomainSpec("general_research", "General Research", "General factual and comparative research."),
)

_DOMAIN_BY_KEY = {row.key: row for row in DOMAINS}
_DOMAIN_BY_LABEL = {row.label.lower(): row for row in DOMAINS}

_TOPIC_TYPE_TO_DOMAIN: dict[str, str] = {
    "technical": "computer_science_programming",
    "science": "science",
    "math": "mathematics",
    "history": "history",
    "law": "law_policy",
    "politics": "law_policy",
    "business": "business_strategy",
    "finance": "business_strategy",
    "medical": "science",
    "education": "general_research",
    "travel": "general_research",
    "general": "general_research",
    "current_events": "general_research",
    "sports": "general_research",
    "combat_sports": "general_research",
    "sports_event": "general_research",
    "animal_care": "science",
    "food": "science",
    "gaming": "creative",
    "books": "creative",
    "tv_shows": "creative",
    "movies": "creative",
    "music": "creative",
    "art": "creative",
    "real_estate": "business_strategy",
    "automotive": "engineering",
    "parenting": "general_research",
    "underground": "general_research",
}

_LEGACY_ALIASES: dict[str, str] = {
    "computer_science": "computer_science_programming",
    "programming": "computer_science_programming",
    "cs": "computer_science_programming",
    "business": "business_strategy",
    "strategy": "business_strategy",
    "law": "law_policy",
    "policy": "law_policy",
    "writing": "writing_rhetoric",
    "rhetoric": "writing_rhetoric",
    "creative_writing": "creative",
    "general": "general_research",
}


def normalize_domain(value: str) -> str:
    raw = str(value or "").strip().lower()
    if not raw:
        return "general_research"
    if raw in _DOMAIN_BY_KEY:
        return raw
    if raw in _DOMAIN_BY_LABEL:
        return _DOMAIN_BY_LABEL[raw].key
    return _LEGACY_ALIASES.get(raw, "general_research")


def domain_for_topic_type(topic_type: str) -> str:
    key = str(topic_type or "").strip().lower()
    mapped = _TOPIC_TYPE_TO_DOMAIN.get(key)
    if mapped:
        return mapped
    return "general_research"


def domain_label(domain_key: str) -> str:
    spec = _DOMAIN_BY_KEY.get(normalize_domain(domain_key))
    return spec.label if spec else "General Research"


def list_domains() -> list[dict[str, str]]:
    return [
        {"key": row.key, "label": row.label, "description": row.description}
        for row in DOMAINS
    ]


def creative_scope_allowed(text: str) -> bool:
    low = str(text or "").strip().lower()
    if not low:
        return True
    # Creative is scoped to narrative arts by Phase 1.
    blocked = ("sports", "movie review", "fandom", "celebrity gossip")
    return not any(token in low for token in blocked)

