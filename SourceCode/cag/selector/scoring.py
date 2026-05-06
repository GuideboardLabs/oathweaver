from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any


_TOKEN_RE = re.compile(r"[a-z0-9]+")


def tokenize(value: str) -> set[str]:
    return set(_TOKEN_RE.findall(str(value or "").lower()))


def _norm_set(values: list[str]) -> set[str]:
    return {str(v or "").strip().lower() for v in values if str(v or "").strip()}


def contains_term(text: str, term: str) -> bool:
    token = str(term or "").strip().lower()
    if not token:
        return False
    return token in str(text or "").lower()


def _extract_terms(continuity_terms: Any) -> list[str]:
    terms: list[str] = []
    for item in continuity_terms or []:
        if isinstance(item, str):
            token = item.strip()
            if token:
                terms.append(token)
        elif isinstance(item, dict):
            for key in ("accepted_terms", "required_terms", "terms"):
                for value in item.get(key, []) if isinstance(item.get(key, []), list) else []:
                    token = str(value or "").strip()
                    if token:
                        terms.append(token)
    return terms


def coerce_concept_groups(continuity_terms: Any) -> list[dict[str, Any]]:
    groups: list[dict[str, Any]] = []
    for idx, item in enumerate(continuity_terms or []):
        if isinstance(item, str):
            token = item.strip()
            if token:
                groups.append({"id": f"concept_{idx+1}", "accepted_terms": [token]})
            continue
        if not isinstance(item, dict):
            continue
        accepted = [str(v).strip() for v in item.get("accepted_terms", []) if str(v).strip()]
        if not accepted:
            accepted = [str(v).strip() for v in item.get("terms", []) if str(v).strip()]
        if not accepted:
            continue
        groups.append(
            {
                "id": str(item.get("id", f"concept_{idx+1}")).strip() or f"concept_{idx+1}",
                "accepted_terms": accepted,
            }
        )
    return groups


@dataclass(frozen=True)
class SelectorScore:
    memory_id: str
    score: float
    concept_overlap: int
    tag_overlap: int
    task_text_overlap: float
    recency_weight: float
    selected: bool

    def as_dict(self) -> dict[str, Any]:
        return {
            "memory_id": self.memory_id,
            "score": self.score,
            "concept_overlap": self.concept_overlap,
            "tag_overlap": self.tag_overlap,
            "task_text_overlap": self.task_text_overlap,
            "recency_weight": self.recency_weight,
            "selected": self.selected,
        }


class ScopedSelector:
    """CAG selector aligned with cag-bench retrieve_scoped scoring."""

    def retrieve_scoped(
        self,
        *,
        task: dict[str, Any],
        rows: list[dict[str, Any]],
        k: int | None = None,
        max_chars: int | None = None,
        return_scores: bool = False,
    ) -> list[dict[str, Any]] | tuple[list[dict[str, Any]], list[dict[str, Any]]]:
        if not rows:
            return ([], []) if return_scores else []

        continuity_groups = coerce_concept_groups(task.get("continuity_terms", []))
        task_tags = _norm_set(task.get("tags", []))
        continuity_terms = _extract_terms(task.get("continuity_terms", []))
        qtext = " ".join(
            [
                str(task.get("title", "") or ""),
                str(task.get("prompt", "") or ""),
                " ".join([str(x) for x in task.get("tags", [])]),
                " ".join(continuity_terms),
            ]
        )
        q_tokens = tokenize(qtext)
        scored: list[dict[str, Any]] = []
        rows_count = len(rows)

        for idx, row in enumerate(rows, start=1):
            row_text = str(row.get("text", "") or "")
            row_tags = _norm_set(row.get("tags", []))
            row_promoted_terms = _norm_set(row.get("promoted_terms", []))

            concept_overlap = 0
            for group in continuity_groups:
                accepted_terms = _norm_set(group.get("accepted_terms", []))
                matched = any(contains_term(row_text, term) for term in accepted_terms) or bool(accepted_terms & row_promoted_terms)
                if matched:
                    concept_overlap += 1

            tag_overlap = len(task_tags & row_tags)
            rtext = " ".join([row_text, str(row.get("scope", "") or ""), " ".join([str(x) for x in row.get("tags", [])]), " ".join([str(x) for x in row.get("promoted_terms", [])])])
            r_tokens = tokenize(rtext)
            union = q_tokens | r_tokens
            task_text_overlap = (len(q_tokens & r_tokens) / len(union)) if union else 0.0
            recency_weight = idx / max(1, rows_count)

            score = (
                3.0 * concept_overlap
                + 1.0 * tag_overlap
                + 0.5 * task_text_overlap
                + 1.0 * recency_weight
            )

            scored.append(
                {
                    "row": row,
                    "score": score,
                    "concept_overlap": concept_overlap,
                    "tag_overlap": tag_overlap,
                    "task_text_overlap": task_text_overlap,
                    "recency_weight": recency_weight,
                }
            )

        scored.sort(key=lambda x: x["score"], reverse=True)
        limit = len(scored) if k is None else max(0, int(k))
        chosen: list[dict[str, Any]] = []
        chosen_ids: set[str] = set()
        total = 0
        for item in scored[:limit]:
            row = item["row"]
            n = len(str(row.get("text", "") or ""))
            if max_chars is not None and total + n > max_chars and chosen:
                continue
            chosen.append(row)
            chosen_ids.add(str(row.get("memory_id", "")))
            total += n

        score_rows: list[dict[str, Any]] = []
        for item in scored:
            row = item["row"]
            score_rows.append(
                SelectorScore(
                    memory_id=str(row.get("memory_id", "")),
                    score=float(item["score"]),
                    concept_overlap=int(item["concept_overlap"]),
                    tag_overlap=int(item["tag_overlap"]),
                    task_text_overlap=float(item["task_text_overlap"]),
                    recency_weight=float(item["recency_weight"]),
                    selected=str(row.get("memory_id", "")) in chosen_ids,
                ).as_dict()
            )
        if return_scores:
            return chosen, score_rows
        return chosen
