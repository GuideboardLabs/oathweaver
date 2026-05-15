from __future__ import annotations

import os
from typing import Any


_TRUE_VALUES = {"1", "true", "yes", "on"}
_FALSE_VALUES = {"0", "false", "no", "off"}


def _env_bool(name: str, default: bool) -> bool:
    raw = str(os.environ.get(name, "")).strip().lower()
    if not raw:
        return default
    if raw in _TRUE_VALUES:
        return True
    if raw in _FALSE_VALUES:
        return False
    return default


def serious_mode_enabled() -> bool:
    return _env_bool("OATHWEAVERX_SERIOUS_MODE", True)


def lane_to_pipeline(lane: str) -> str:
    key = str(lane or "").strip().lower()
    if not key:
        return "research_pipeline"
    mapping = {
        "research": "research_pipeline",
        "project": "build_pipeline",
        "ui": "build_pipeline",
        "conversation": "conversation_pipeline",
        "make_app": "build_pipeline",
        "make_doc": "build_pipeline",
        "make_plan": "build_pipeline",
        "make_tool": "build_pipeline",
        "make_creative": "build_pipeline",
        "make_content": "build_pipeline",
        "make_specialist": "build_pipeline",
        "make_longform": "build_pipeline",
        "make_desktop_app": "build_pipeline",
    }
    return mapping.get(key, f"{key}_pipeline")


def normalize_domain(value: str) -> str:
    text = str(value or "").strip()
    if not text:
        return "general"
    return text.lower()


def enrich_phase0_aliases(payload: dict[str, Any]) -> dict[str, Any]:
    row = dict(payload)
    lane = str(row.get("lane", "")).strip()
    if lane and "pipeline" not in row:
        row["pipeline"] = lane_to_pipeline(lane)

    topic_type = str(row.get("topic_type", "")).strip()
    if topic_type and "domain" not in row:
        row["domain"] = normalize_domain(topic_type)

    # Foraging -> Research terminology bridge.
    if "foraging_active_jobs" in row and "research_active_jobs" not in row:
        row["research_active_jobs"] = row.get("foraging_active_jobs")
    if "foraging_paused" in row and "research_paused" not in row:
        row["research_paused"] = row.get("foraging_paused")
    if "foraging_yielding" in row and "research_yielding" not in row:
        row["research_yielding"] = row.get("foraging_yielding")
    if "foraging_completion_unread" in row and "research_completion_unread" not in row:
        row["research_completion_unread"] = row.get("foraging_completion_unread")
    if "foraging_last_completed_at" in row and "research_last_completed_at" not in row:
        row["research_last_completed_at"] = row.get("foraging_last_completed_at")
    if "foraging_updated_at" in row and "research_updated_at" not in row:
        row["research_updated_at"] = row.get("foraging_updated_at")
    return row


__all__ = [
    "enrich_phase0_aliases",
    "lane_to_pipeline",
    "normalize_domain",
    "serious_mode_enabled",
]
