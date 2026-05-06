from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class MakeTypeSpec:
    key: str
    label: str
    family: str


MAKE_TYPES: tuple[MakeTypeSpec, ...] = (
    # Programming
    MakeTypeSpec("cli_tool", "CLI tool", "programming"),
    MakeTypeSpec("tui_app", "TUI app", "programming"),
    MakeTypeSpec("web_app", "Web app", "programming"),
    MakeTypeSpec("desktop_app", "Desktop app", "programming"),
    MakeTypeSpec("library_sdk", "Library/SDK", "programming"),
    MakeTypeSpec("backend_service", "Backend service", "programming"),
    MakeTypeSpec("full_application", "Full application", "programming"),
    MakeTypeSpec("benchmark_suite", "Benchmark suite", "programming"),
    MakeTypeSpec("developer_tool", "Developer tool", "programming"),
    MakeTypeSpec("data_pipeline", "Data pipeline", "programming"),
    MakeTypeSpec("model_runtime_system", "Model/runtime system", "programming"),
    # Writing serious
    MakeTypeSpec("academic_paper", "Academic paper", "writing_serious"),
    MakeTypeSpec("technical_whitepaper", "Technical whitepaper", "writing_serious"),
    MakeTypeSpec("official_report", "Official report", "writing_serious"),
    MakeTypeSpec("biography", "Biography", "writing_serious"),
    MakeTypeSpec("documentation", "Documentation", "writing_serious"),
    MakeTypeSpec("proposal", "Proposal", "writing_serious"),
    MakeTypeSpec("research_memo", "Research memo", "writing_serious"),
    MakeTypeSpec("essay", "Essay", "writing_serious"),
    # Writing creative
    MakeTypeSpec("fiction", "Fiction", "writing_creative"),
    MakeTypeSpec("worldbuilding", "Worldbuilding", "writing_creative"),
    MakeTypeSpec("script_narrative", "Script/narrative", "writing_creative"),
    # Strategy / planning
    MakeTypeSpec("product_plan", "Product plan", "strategy_planning"),
    MakeTypeSpec("architecture_plan", "Architecture plan", "strategy_planning"),
    MakeTypeSpec("roadmap", "Roadmap", "strategy_planning"),
    MakeTypeSpec("risk_assessment", "Risk assessment", "strategy_planning"),
    MakeTypeSpec("decision_memo", "Decision memo", "strategy_planning"),
    MakeTypeSpec("benchmark_plan", "Benchmark plan", "strategy_planning"),
    # Research artifacts
    MakeTypeSpec("research_brief", "Research brief", "research_artifact"),
    MakeTypeSpec("literature_review", "Literature review", "research_artifact"),
    MakeTypeSpec("source_map", "Source map", "research_artifact"),
    MakeTypeSpec("annotated_bibliography", "Annotated bibliography", "research_artifact"),
    MakeTypeSpec("comparative_analysis", "Comparative analysis", "research_artifact"),
    MakeTypeSpec("fact_base", "Fact base", "research_artifact"),
    MakeTypeSpec("timeline", "Timeline", "research_artifact"),
)

_SPEC_BY_KEY = {row.key: row for row in MAKE_TYPES}
_ALIASES: dict[str, str] = {
    "tool": "developer_tool",
    "make_tool": "developer_tool",
    "webapp": "web_app",
    "standalone_app": "full_application",
    "app": "full_application",
    "desktop": "desktop_app",
    "api": "backend_service",
    "report": "official_report",
    "brief": "research_brief",
    "essay_long": "essay",
    "essay_short": "essay",
    "guide": "documentation",
    "tutorial": "documentation",
    "novel": "fiction",
    "screenplay": "script_narrative",
    "memoir": "biography",
    "book": "biography",
    "blog": "research_memo",
    "social_post": "research_brief",
    "newsletter": "research_memo",
    "press_release": "official_report",
    "game_design_doc": "architecture_plan",
    "medical": "research_brief",
    "finance": "research_brief",
    "sports": "research_brief",
    "history": "research_brief",
}


def normalize_make_type(value: str) -> str:
    key = str(value or "").strip().lower().replace(" ", "_").replace("-", "_")
    if key in _SPEC_BY_KEY:
        return key
    return _ALIASES.get(key, "")


def infer_make_type(*, text: str, target: str = "", lane: str = "") -> str:
    resolved_target = normalize_make_type(target)
    if resolved_target:
        return resolved_target
    low = str(text or "").lower()
    lane_key = str(lane or "").strip().lower()
    if "benchmark" in low:
        return "benchmark_suite"
    if any(token in low for token in ("sdk", "library")):
        return "library_sdk"
    if any(token in low for token in ("roadmap", "strategy", "plan")):
        return "product_plan"
    if any(token in low for token in ("whitepaper", "paper")):
        return "technical_whitepaper"
    if "timeline" in low:
        return "timeline"
    if lane_key in {"make_app", "ui"}:
        return "web_app"
    if lane_key == "make_tool":
        return "developer_tool"
    if lane_key == "make_desktop_app":
        return "desktop_app"
    if lane_key.startswith("make_"):
        return "documentation"
    return "research_brief"


def list_make_types() -> list[dict[str, str]]:
    return [{"key": row.key, "label": row.label, "family": row.family} for row in MAKE_TYPES]


def make_type_spec(value: str) -> MakeTypeSpec:
    key = normalize_make_type(value)
    if key and key in _SPEC_BY_KEY:
        return _SPEC_BY_KEY[key]
    return _SPEC_BY_KEY["research_brief"]

