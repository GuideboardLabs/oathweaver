from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from cag.lifecycle import normalize_human_status
from cag.memory_store import normalize_memory_type
from cag.selector import tokenize


PROMOTABLE_TYPES: tuple[str, ...] = ("decision", "fact", "constraint", "lesson", "benchmark_implication")


@dataclass(frozen=True)
class PromotionDecision:
    accepted: bool
    reasons: list[str]
    confidence: float
    normalized_candidate: dict[str, Any]

    def as_dict(self) -> dict[str, Any]:
        return {
            "accepted": self.accepted,
            "reasons": list(self.reasons),
            "confidence": float(self.confidence),
            "normalized_candidate": dict(self.normalized_candidate),
        }


class PromotionGate:
    """Strict durable-memory gate for CAG rows."""

    def evaluate(
        self,
        *,
        candidate: dict[str, Any],
        existing_rows: list[dict[str, Any]],
        contradictions: list[dict[str, Any]],
        contradiction_budget: dict[str, Any],
    ) -> PromotionDecision:
        row = self._normalize_candidate(candidate)
        reasons: list[str] = []

        if not row["text"]:
            reasons.append("empty_text")
        if len(row["text"]) > 2200:
            reasons.append("too_long_not_compact")
        if row["type"] not in PROMOTABLE_TYPES:
            reasons.append("unsupported_memory_type")
        if not row["scope"]:
            reasons.append("missing_scope")
        if not row["tags"]:
            reasons.append("missing_tags")
        if not self._has_validation_signal(row.get("validation", {})):
            reasons.append("insufficient_validation")
        if self._is_redundant(row, existing_rows):
            reasons.append("redundant")

        contradiction_labels = [str(x.get("label", "")).strip().lower() for x in contradictions]
        if "error" in contradiction_labels:
            reasons.append("contradiction_error")
        if bool(contradiction_budget.get("exceeded", False)):
            reasons.append("contradiction_budget_exceeded")

        accepted = not reasons
        if accepted:
            row["status"] = "accepted"
        else:
            row["status"] = "candidate"

        return PromotionDecision(
            accepted=accepted,
            reasons=reasons,
            confidence=float(row.get("confidence", 0.0) or 0.0),
            normalized_candidate=row,
        )

    def _normalize_candidate(self, candidate: dict[str, Any]) -> dict[str, Any]:
        row = dict(candidate or {})
        row["text"] = str(row.get("text", "")).strip()
        row["scope"] = str(row.get("scope", "")).strip()
        row["scope_level"] = str(row.get("scope_level", "project")).strip().lower() or "project"
        row["type"] = normalize_memory_type(str(row.get("type", row.get("memory_type", "decision"))))
        row["status"] = str(row.get("status", "candidate")).strip().lower() or "candidate"
        row["human_status"] = normalize_human_status(str(row.get("human_status", "unreviewed")))
        row["source"] = str(row.get("source", "promotion_gate")).strip() or "promotion_gate"
        row["tags"] = self._clean_lower_tokens(row.get("tags", []))
        row["promoted_terms"] = self._clean_lower_tokens(row.get("promoted_terms", []))
        row["supersedes"] = self._clean_tokens(row.get("supersedes", []))
        row["superseded_by"] = self._clean_tokens(row.get("superseded_by", []))
        row["evidence"] = [dict(x) for x in row.get("evidence", []) if isinstance(x, dict)]
        row["validation"] = dict(row.get("validation", {})) if isinstance(row.get("validation", {}), dict) else {}
        row["contradictions"] = [dict(x) for x in row.get("contradictions", []) if isinstance(x, dict)]
        raw_conf = row.get("confidence", 0.0)
        try:
            conf = float(raw_conf)
        except Exception:
            conf = 0.0
        row["confidence"] = max(0.0, min(1.0, conf))
        return row

    @staticmethod
    def _clean_tokens(values: Any) -> list[str]:
        out: list[str] = []
        for value in values or []:
            token = str(value or "").strip()
            if token and token not in out:
                out.append(token)
        return out

    @staticmethod
    def _clean_lower_tokens(values: Any) -> list[str]:
        out: list[str] = []
        for value in values or []:
            token = str(value or "").strip().lower()
            if token and token not in out:
                out.append(token)
        return out

    @staticmethod
    def _has_validation_signal(validation: dict[str, Any]) -> bool:
        signals = {
            "task_metadata",
            "user_accepted",
            "tests_passed",
            "has_citation",
            "auditor_approved",
            "benchmark_backed",
            "watchtower_validated",
        }
        for key in signals:
            if bool(validation.get(key, False)):
                return True
        return False

    def _is_redundant(self, candidate: dict[str, Any], rows: list[dict[str, Any]]) -> bool:
        text_tokens = tokenize(str(candidate.get("text", "")))
        if not text_tokens:
            return False
        cand_scope = str(candidate.get("scope", "")).strip()
        cand_type = str(candidate.get("type", "")).strip()

        for row in rows:
            if cand_scope and str(row.get("scope", "")).strip() and str(row.get("scope", "")).strip() != cand_scope:
                continue
            if cand_type and str(row.get("type", row.get("memory_type", ""))).strip() and str(row.get("type", row.get("memory_type", ""))).strip() != cand_type:
                continue
            existing_tokens = tokenize(str(row.get("text", "")))
            union = text_tokens | existing_tokens
            if not union:
                continue
            similarity = len(text_tokens & existing_tokens) / len(union)
            if similarity >= 0.92:
                return True
        return False
