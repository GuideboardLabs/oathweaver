from __future__ import annotations

import re
from typing import Any

from cag.selector import ScopedSelector


def resolved_pipeline_domain(make_type: str, inferred_domain: str, resolve_domain_fn) -> str:
    return resolve_domain_fn(str(make_type or ""), str(inferred_domain or ""))


def select_context_memory_rows(
    selector: ScopedSelector,
    *,
    payload: dict[str, Any],
    project_rows: list[dict[str, Any]],
    domain_rows: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    candidate_rows = list(project_rows) + list(domain_rows)
    deduped_rows: list[dict[str, Any]] = []
    seen_ids: set[str] = set()
    for row in candidate_rows:
        memory_id = str(row.get("memory_id", "")).strip()
        if memory_id and memory_id in seen_ids:
            continue
        if memory_id:
            seen_ids.add(memory_id)
        deduped_rows.append(row)
    domain_tag = str(payload.get("domain", "general_research")).strip() or "general_research"
    make_type_tag = str(payload.get("target", "")).strip().lower()
    return selector.retrieve_scoped(
        task={
            "title": str(payload.get("text", "")),
            "prompt": str(payload.get("text", "")),
            "tags": [token for token in (domain_tag, make_type_tag) if token],
            "continuity_terms": [],
            "domain": domain_tag,
        },
        rows=deduped_rows,
        k=40,
    )


def candidate_tags(payload: dict[str, Any], scope_row: dict[str, Any]) -> list[str]:
    raw = [
        str(payload.get("lane", "")).strip(),
        str(payload.get("topic_type", "")).strip(),
        str(payload.get("query_mode", "")).strip(),
        str(payload.get("query_complexity", "")).strip(),
        str(scope_row.get("domain", "")).strip(),
        str(scope_row.get("topic", "")).strip(),
    ]
    out: list[str] = []
    for item in raw:
        token = item.lower().replace(" ", "_")
        if token and token not in out:
            out.append(token)
    return out


def promoted_terms(text: str, *, limit: int = 12) -> list[str]:
    terms: list[str] = []
    for token in re.findall(r"[a-z0-9_\\-]{4,}", str(text or "").lower()):
        if token in terms:
            continue
        terms.append(token)
        if len(terms) >= max(1, int(limit)):
            break
    return terms


def infer_memory_type(summary: str, payload: dict[str, Any]) -> str:
    low = str(summary or "").lower()
    lane = str(payload.get("lane", "")).strip().lower()
    if "benchmark" in low or lane == "project":
        return "benchmark_implication"
    if any(word in low for word in ("must", "required", "constraint", "cannot", "never")):
        return "constraint"
    if any(word in low for word in ("we decided", "decision", "choose", "selected")):
        return "decision"
    if any(word in low for word in ("learned", "lesson", "retrospective")):
        return "lesson"
    return "fact"

