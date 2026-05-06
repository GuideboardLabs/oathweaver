from __future__ import annotations


RESEARCH_FOCUS_VALUES: tuple[str, ...] = (
    "domain_focused",
    "product_focused",
    "implementation_focused",
    "evidence_focused",
    "benchmark_focused",
    "risk_focused",
)

_RESEARCH_FOCUS_SET = set(RESEARCH_FOCUS_VALUES)
_ALIASES: dict[str, str] = {
    "domain-focused": "domain_focused",
    "product-focused": "product_focused",
    "implementation-focused": "implementation_focused",
    "evidence-focused": "evidence_focused",
    "benchmark-focused": "benchmark_focused",
    "risk-focused": "risk_focused",
}


def normalize_research_focus(value: str) -> str:
    key = str(value or "").strip().lower().replace(" ", "_")
    key = _ALIASES.get(key, key)
    return key if key in _RESEARCH_FOCUS_SET else "domain_focused"


def infer_research_focus(
    *,
    text: str,
    query_mode: str = "",
    pipeline: str = "",
    make_type: str = "",
) -> str:
    low = str(text or "").lower()
    mode = str(query_mode or "").strip().lower()
    pipe = str(pipeline or "").strip().lower()
    mk = str(make_type or "").strip().lower()

    if "benchmark" in low or mode == "deep_research" and "ablation" in low:
        return "benchmark_focused"
    if any(token in low for token in ("risk", "failure mode", "tradeoff", "threat model")):
        return "risk_focused"
    if any(token in low for token in ("evidence", "citation", "source", "prove", "verify")):
        return "evidence_focused"
    if pipe == "build_pipeline" or mode == "workspace_code":
        return "implementation_focused"
    if mk in {"product_plan", "roadmap", "full_application", "web_app", "desktop_app"}:
        return "product_focused"
    return "domain_focused"


def list_research_focus() -> list[str]:
    return list(RESEARCH_FOCUS_VALUES)

