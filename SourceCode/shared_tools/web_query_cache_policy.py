from __future__ import annotations

from typing import Any

from shared_tools.fact_policy import classify_fact_volatility


def should_bypass_query_cache(query: str, note: str, explicit_bypass: bool) -> bool:
    if explicit_bypass:
        return True
    raw = f"{query} {note}".lower()
    return any(token in raw for token in ("refresh", "again"))


def query_cache_ttl_sec(query: str, topic_type: str) -> int:
    low = str(query or "").lower()
    live_markers = (
        "fight night",
        "live score",
        "live result",
        "live update",
        "who won",
        "score right now",
        "tonight",
        "main event",
        "kickoff",
        "tipoff",
    )
    if any(marker in low for marker in live_markers):
        return 10 * 60
    volatility = classify_fact_volatility(query, topic_type, query)
    if volatility in {"volatile", "semi_volatile"}:
        return 2 * 60 * 60
    return 24 * 60 * 60


def query_cache_settings(settings: dict[str, Any]) -> dict[str, Any]:
    keys = (
        "provider",
        "mode",
        "max_results",
        "num_ctx",
        "temperature",
        "query_expansion_enabled",
        "query_expansion_variants",
        "query_decomposition_enabled",
        "query_decomposition_max_sub",
        "crawl_enabled",
        "crawl_depth",
        "crawl_max_pages",
        "crawl_links_per_page",
        "crawl_timeout_sec",
        "context_min_source_score",
        "min_quality_sources",
        "source_scoring_enabled",
        "conflict_detection_enabled",
        "iterative_search_enabled",
        "iterative_search_time_budget_sec",
        "user_images",
        "user_image_count",
        "safesearch",
    )
    out: dict[str, Any] = {}
    for key in keys:
        if key in settings:
            out[key] = settings.get(key)
    return out


def cache_disclosure(age_sec: int) -> str:
    mins = max(0, int(round(age_sec / 60.0)))
    return f"Last retrieved {mins} minute{'s' if mins != 1 else ''} ago."

