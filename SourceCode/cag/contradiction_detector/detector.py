from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from cag.selector import tokenize


CONTRADICTION_LABELS: tuple[str, ...] = (
    "error",
    "intentional revision",
    "scope mismatch",
    "outdated memory",
    "ambiguous terminology",
)

_POSITIVE_HINTS = {"enable", "use", "allow", "required", "must", "always", "true", "increase"}
_NEGATIVE_HINTS = {"disable", "avoid", "deny", "forbid", "never", "false", "decrease", "remove", "not"}


@dataclass(frozen=True)
class ContradictionRecord:
    label: str
    existing_memory_id: str
    reason: str
    score: float

    def as_dict(self) -> dict[str, Any]:
        return {
            "label": self.label,
            "existing_memory_id": self.existing_memory_id,
            "reason": self.reason,
            "score": self.score,
        }


class ContradictionDetector:
    def detect(
        self,
        *,
        candidate: dict[str, Any],
        existing_rows: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        out: list[dict[str, Any]] = []
        candidate_text = str(candidate.get("text", "") or "").strip()
        if not candidate_text:
            return out

        candidate_tokens = tokenize(candidate_text)
        candidate_scope_level = str(candidate.get("scope_level", "project")).strip().lower()
        candidate_supersedes = {str(x).strip() for x in candidate.get("supersedes", []) if str(x).strip()}

        for row in existing_rows:
            existing_text = str(row.get("text", "") or "").strip()
            if not existing_text:
                continue
            existing_id = str(row.get("memory_id", "")).strip()
            if existing_id and existing_id == str(candidate.get("memory_id", "")).strip():
                continue

            existing_tokens = tokenize(existing_text)
            union = candidate_tokens | existing_tokens
            if not union:
                continue
            overlap = len(candidate_tokens & existing_tokens) / len(union)
            if overlap < 0.08:
                continue

            label = ""
            reason = ""

            if existing_id and existing_id in candidate_supersedes:
                label = "intentional revision"
                reason = "candidate_explicitly_supersedes_existing"
            else:
                existing_scope_level = str(row.get("scope_level", "project")).strip().lower()
                if existing_scope_level != candidate_scope_level and overlap >= 0.20:
                    label = "scope mismatch"
                    reason = "similar_claim_but_different_scope_levels"
                else:
                    existing_status = str(row.get("status", "accepted")).strip().lower()
                    if existing_status in {"deprecated", "superseded", "expired"}:
                        label = "outdated memory"
                        reason = "candidate_matches_non_active_memory"
                    else:
                        polarity = self._polarity_conflict(candidate_tokens, existing_tokens)
                        if polarity and overlap >= 0.12:
                            label = "error"
                            reason = "possible_direct_conflict"
                        elif overlap >= 0.45:
                            label = "ambiguous terminology"
                            reason = "high_lexical_overlap_without_clear_conflict"

            if not label:
                continue
            out.append(
                ContradictionRecord(
                    label=label,
                    existing_memory_id=existing_id,
                    reason=reason,
                    score=float(overlap),
                ).as_dict()
            )

        out.sort(key=lambda x: float(x.get("score", 0.0)), reverse=True)
        return out

    @staticmethod
    def contradiction_budget(*, contradictions: list[dict[str, Any]], non_error_budget: int) -> dict[str, Any]:
        non_error_count = 0
        for row in contradictions:
            label = str(row.get("label", "")).strip().lower()
            if label and label != "error":
                non_error_count += 1
        budget = max(0, int(non_error_budget))
        return {
            "non_error_budget": budget,
            "non_error_count": non_error_count,
            "exceeded": non_error_count > budget,
        }

    @staticmethod
    def _polarity_conflict(a: set[str], b: set[str]) -> bool:
        a_pos = bool(a & _POSITIVE_HINTS)
        a_neg = bool(a & _NEGATIVE_HINTS)
        b_pos = bool(b & _POSITIVE_HINTS)
        b_neg = bool(b & _NEGATIVE_HINTS)
        return (a_pos and b_neg) or (a_neg and b_pos)
