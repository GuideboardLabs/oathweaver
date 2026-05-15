from __future__ import annotations

RESEARCH_PERSONAS = [
    ("market_analyst", "Focus on market dynamics, alternatives, and strategic positioning."),
    ("technical_researcher", "Focus on technical feasibility, architecture tradeoffs, and bottlenecks."),
    ("risk_researcher", "Focus on risks, failure modes, constraints, and mitigation plans."),
    ("execution_planner", "Focus on practical sequencing, milestones, and resource-fit execution."),
]
DEFAULT_DIRECTIVES = {persona: directive for persona, directive in RESEARCH_PERSONAS}

ANALYSIS_PROFILE_TECHNICAL = "technical_analysis"
ANALYSIS_PROFILE_GENERAL = "general_analysis"
ANALYSIS_PROFILE_MEDICAL = "medical_analysis"
ANALYSIS_PROFILE_PARENTING = "parenting_analysis"
ANALYSIS_PROFILE_FINANCE = "finance_analysis"
ANALYSIS_PROFILE_SPORTS = "sports_analysis"
ANALYSIS_PROFILE_COMBAT_SPORTS = "combat_sports_analysis"
ANALYSIS_PROFILE_SPORTS_EVENT = "sports_event_analysis"
ANALYSIS_PROFILE_HISTORY = "history_analysis"
ANALYSIS_PROFILE_SCIENCE = "science_analysis"
ANALYSIS_PROFILE_MATH = "math_analysis"
ANALYSIS_PROFILE_POLITICS = "politics_analysis"
ANALYSIS_PROFILE_CURRENT_EVENTS = "current_events_analysis"
ANALYSIS_PROFILE_UNDERGROUND = "underground_analysis"
ANALYSIS_PROFILE_ANIMAL_CARE = "animal_care_analysis"
ANALYSIS_PROFILE_BUSINESS = "business_analysis"
ANALYSIS_PROFILE_LAW = "law_analysis"
ANALYSIS_PROFILE_EDUCATION = "education_analysis"
ANALYSIS_PROFILE_TRAVEL = "travel_analysis"
ANALYSIS_PROFILE_FOOD = "food_analysis"
ANALYSIS_PROFILE_GAMING = "gaming_analysis"
ANALYSIS_PROFILE_BOOKS = "books_analysis"
ANALYSIS_PROFILE_REAL_ESTATE = "real_estate_analysis"
ANALYSIS_PROFILE_AUTOMOTIVE = "automotive_analysis"
ANALYSIS_PROFILE_TV_SHOWS = "tv_shows_analysis"
ANALYSIS_PROFILE_MOVIES = "movies_analysis"
ANALYSIS_PROFILE_MUSIC = "music_analysis"
ANALYSIS_PROFILE_ART = "art_analysis"

STATISTICAL_ANALYSIS_PERSONA = "statistical_analysis"
STATISTICAL_ANALYSIS_DIRECTIVE = (
    "OUTPUT CONTRACT: Return ONLY quantitative findings from sources. "
    "Allowed finding types: prevalence or incidence rates, effect sizes or risk ratios, measurable thresholds, "
    "comparative rates across groups/interventions, longitudinal trends with time windows, and uncertainty bounds "
    "or confidence intervals when provided. If sources contain no quantitative data, return exactly this line under "
    "Findings: 'No quantitative data extractable from available sources.' "
    "Do NOT restate mechanism/prevention/management prose covered by other personas. Numeric signal only."
)
LEGAL_ANALYSIS_PERSONA = "legal_analysis"
LEGAL_ANALYSIS_DIRECTIVE = (
    "Focus on legal and compliance constraints, jurisdiction caveats, and explicit risk language. "
    "Flag where professional legal counsel is required."
)
STATISTICAL_ANALYSIS_MODEL = "hf.co/unsloth/Qwen3-8B-GGUF:UD-Q5_K_XL"
LEGAL_ANALYSIS_MODEL = "hf.co/unsloth/Qwen3-8B-GGUF:UD-Q5_K_XL"

TOPIC_TYPE_TO_PROFILE: dict[str, str] = {
    "sports": ANALYSIS_PROFILE_SPORTS,
    "combat_sports": ANALYSIS_PROFILE_COMBAT_SPORTS,
    "sports_event": ANALYSIS_PROFILE_SPORTS_EVENT,
    "technical": ANALYSIS_PROFILE_TECHNICAL,
    "medical": ANALYSIS_PROFILE_MEDICAL,
    "animal_care": ANALYSIS_PROFILE_ANIMAL_CARE,
    "finance": ANALYSIS_PROFILE_FINANCE,
    "history": ANALYSIS_PROFILE_HISTORY,
    "science": ANALYSIS_PROFILE_SCIENCE,
    "math": ANALYSIS_PROFILE_MATH,
    "politics": ANALYSIS_PROFILE_POLITICS,
    "current_events": ANALYSIS_PROFILE_CURRENT_EVENTS,
    "general": ANALYSIS_PROFILE_GENERAL,
    "underground": ANALYSIS_PROFILE_UNDERGROUND,
    "parenting": ANALYSIS_PROFILE_PARENTING,
    "business": ANALYSIS_PROFILE_BUSINESS,
    "law": ANALYSIS_PROFILE_LAW,
    "education": ANALYSIS_PROFILE_EDUCATION,
    "travel": ANALYSIS_PROFILE_TRAVEL,
    "food": ANALYSIS_PROFILE_FOOD,
    "gaming": ANALYSIS_PROFILE_GAMING,
    "books": ANALYSIS_PROFILE_BOOKS,
    "real_estate": ANALYSIS_PROFILE_REAL_ESTATE,
    "automotive": ANALYSIS_PROFILE_AUTOMOTIVE,
    "tv_shows": ANALYSIS_PROFILE_TV_SHOWS,
    "movies": ANALYSIS_PROFILE_MOVIES,
    "music": ANALYSIS_PROFILE_MUSIC,
    "art": ANALYSIS_PROFILE_ART,
}

