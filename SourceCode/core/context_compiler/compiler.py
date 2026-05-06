from __future__ import annotations

import os
import re
import uuid
from datetime import datetime, timezone
from typing import Any

from core.context_pack import ContextPackStore

from .profiles import profile_for_stage


_TOKEN_RE = re.compile(r"[a-z0-9_\-]+")
_VALID_MEMORY_STATUSES = {"accepted", "user-confirmed", "benchmark-derived", "watchtower-derived"}


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _to_tokens(text: str) -> set[str]:
    return set(_TOKEN_RE.findall(str(text or "").lower()))


def _approx_tokens(text: str) -> int:
    words = _TOKEN_RE.findall(str(text or ""))
    if not words:
        return 0
    # lightweight estimate for stage-budget checks
    return max(1, int(round(len(words) * 1.35)))


class ContextCompiler:
    """Compiles role-scoped, token-budgeted context packs per stage."""

    def __init__(self, *, context_pack_store: ContextPackStore) -> None:
        self.context_pack_store = context_pack_store

    def compile(
        self,
        *,
        run_id: str,
        pipeline: str,
        stage: str,
        input_payload: dict[str, Any],
        stage_state: dict[str, Any],
        project_kernel: dict[str, Any],
        memory_rows: list[dict[str, Any]],
        decision_rows: list[dict[str, Any]],
        benchmark_lessons: list[str],
        output_contract: str,
        hardware_token_budget: int | None = None,
    ) -> dict[str, Any]:
        profile = profile_for_stage(stage)
        budget = self._resolve_budget(hardware_token_budget)
        knowledge = project_kernel.get("knowledge_spine", {}) if isinstance(project_kernel.get("knowledge_spine", {}), dict) else {}

        selected_mem, excluded_reasons = self._select_memory(
            stage=stage,
            profile=profile,
            budget=budget,
            query_text=self._build_query_text(input_payload, stage_state, stage),
            rows=memory_rows,
        )
        selected_decisions = self._select_decisions(
            profile=profile,
            budget=budget,
            used_tokens=sum(_approx_tokens(str(row.get("text", ""))) for row in selected_mem),
            rows=decision_rows,
            query_text=self._build_query_text(input_payload, stage_state, stage),
        )

        included_ids = [str(row.get("memory_id", "")).strip() for row in selected_mem if str(row.get("memory_id", "")).strip()]
        included_ids.extend([str(row.get("decision_id", "")).strip() for row in selected_decisions if str(row.get("decision_id", "")).strip()])

        memory_snippets = []
        for row in selected_mem:
            memory_snippets.append(
                {
                    "id": str(row.get("memory_id", "")).strip(),
                    "kind": "memory",
                    "type": str(row.get("type", row.get("memory_type", ""))).strip(),
                    "scope_level": str(row.get("scope_level", "")).strip(),
                    "confidence": float(row.get("confidence", 0.0) or 0.0),
                    "text": str(row.get("text", "")).strip()[:320],
                }
            )
        for row in selected_decisions:
            memory_snippets.append(
                {
                    "id": str(row.get("decision_id", "")).strip(),
                    "kind": "decision_ledger",
                    "type": str(row.get("decision_type", "")).strip(),
                    "scope_level": str(row.get("scope_level", "")).strip(),
                    "confidence": 1.0,
                    "text": str(row.get("decision_text", "")).strip()[:320],
                }
            )

        payload = {
            "context_pack_id": self._new_context_pack_id(stage),
            "run_id": str(run_id),
            "pipeline": str(pipeline),
            "stage": str(stage),
            "specialist_role": profile.specialist_role,
            "project": str(input_payload.get("project_slug", "general")).strip() or "general",
            "domain": str(knowledge.get("domain", input_payload.get("topic_type", "general"))).strip(),
            "topic": str(knowledge.get("topic", input_payload.get("topic_type", "general"))).strip(),
            "thread": str(knowledge.get("thread", "")).strip(),
            "token_budget": budget,
            "output_contract": str(output_contract or stage).strip() or str(stage),
            "included_memory": included_ids,
            "excluded_memory_reasoning": excluded_reasons,
            "memory_snippets": memory_snippets,
            "retrieval_results": self._build_retrieval_results(stage=stage, stage_state=stage_state),
            "benchmark_lessons": [str(x).strip() for x in benchmark_lessons if str(x).strip()][:10],
            "few_shot_examples": self._few_shots_for_stage(stage),
            "created_at": _now_iso(),
        }
        return self.context_pack_store.persist(payload)

    def _select_memory(
        self,
        *,
        stage: str,
        profile: Any,
        budget: int,
        query_text: str,
        rows: list[dict[str, Any]],
    ) -> tuple[list[dict[str, Any]], list[str]]:
        query_tokens = _to_tokens(query_text)
        scored: list[tuple[float, dict[str, Any]]] = []
        excluded_reasons: list[str] = []

        for row in rows:
            status = str(row.get("status", "")).strip().lower()
            if status not in _VALID_MEMORY_STATUSES:
                excluded_reasons.append(f"excluded {row.get('memory_id', '')}: status={status or 'unknown'} not validated")
                continue
            human_status = str(row.get("human_status", "")).strip().lower()
            if human_status == "rejected":
                excluded_reasons.append(f"excluded {row.get('memory_id', '')}: human_status=rejected")
                continue

            rtype = str(row.get("type", row.get("memory_type", ""))).strip().lower()
            if profile.preferred_memory_types and rtype not in set(profile.preferred_memory_types):
                excluded_reasons.append(f"excluded {row.get('memory_id', '')}: type={rtype or 'unknown'} outside stage profile")
                continue

            scope_level = str(row.get("scope_level", "")).strip().lower()
            if profile.preferred_scope_levels and scope_level and scope_level not in set(profile.preferred_scope_levels):
                excluded_reasons.append(
                    f"excluded {row.get('memory_id', '')}: scope_level={scope_level} outside stage profile"
                )
                continue

            text = str(row.get("text", "")).strip()
            row_tokens = _to_tokens(text)
            overlap = 0.0
            if query_tokens and row_tokens:
                overlap = len(query_tokens & row_tokens) / len(query_tokens | row_tokens)

            type_bonus = 0.0
            if rtype in profile.preferred_memory_types:
                type_bonus = float(len(profile.preferred_memory_types) - profile.preferred_memory_types.index(rtype)) * 0.15
            confidence = float(row.get("confidence", 0.0) or 0.0)
            recency = self._recency_weight(row)
            score = (2.2 * overlap) + type_bonus + (0.8 * confidence) + (0.4 * recency)
            scored.append((score, row))

        scored.sort(key=lambda x: x[0], reverse=True)
        selected: list[dict[str, Any]] = []
        used_tokens = 0
        for _, row in scored:
            text = str(row.get("text", "")).strip()
            candidate_tokens = _approx_tokens(text)
            if selected and used_tokens + candidate_tokens > budget:
                excluded_reasons.append(
                    f"excluded {row.get('memory_id', '')}: token_budget_exceeded_for_stage_{stage}"
                )
                continue
            selected.append(row)
            used_tokens += candidate_tokens
            if used_tokens >= budget:
                break
        return selected[:18], excluded_reasons[:24]

    def _select_decisions(
        self,
        *,
        profile: Any,
        budget: int,
        used_tokens: int,
        rows: list[dict[str, Any]],
        query_text: str,
    ) -> list[dict[str, Any]]:
        if not profile.include_decision_ledger:
            return []

        query_tokens = _to_tokens(query_text)
        scored: list[tuple[float, dict[str, Any]]] = []
        for row in rows:
            text = str(row.get("decision_text", "")).strip()
            row_tokens = _to_tokens(text)
            overlap = 0.0
            if query_tokens and row_tokens:
                overlap = len(query_tokens & row_tokens) / len(query_tokens | row_tokens)
            score = (2.0 * overlap) + (0.6 * self._recency_weight(row))
            scored.append((score, row))
        scored.sort(key=lambda x: x[0], reverse=True)

        selected: list[dict[str, Any]] = []
        token_count = int(used_tokens)
        for _, row in scored:
            row_tokens = _approx_tokens(str(row.get("decision_text", "")))
            if token_count + row_tokens > budget:
                continue
            selected.append(row)
            token_count += row_tokens
            if len(selected) >= 6:
                break
        return selected

    @staticmethod
    def _few_shots_for_stage(stage: str) -> list[dict[str, str]]:
        mapping = {
            "planner": [{"id": "planner_a", "hint": "Produce explicit file-level plan before patching."}],
            "source_discovery": [{"id": "research_a", "hint": "Prefer official docs and primary evidence."}],
            "evidence_analysis": [{"id": "analysis_a", "hint": "Separate observations from assumptions."}],
            "nuance_pass": [{"id": "skeptic_a", "hint": "List contradictions and unresolved risks."}],
            "synthesis": [{"id": "synth_a", "hint": "Tie claims to evidence and uncertainty."}],
            "verification": [{"id": "verify_a", "hint": "Highlight behavior changes and residual risk."}],
            "cag_promotion_gate": [{"id": "memory_a", "hint": "Promote only validated, scoped, compact memory."}],
        }
        return mapping.get(str(stage).strip(), [{"id": "default", "hint": "Follow stage output contract strictly."}])

    @staticmethod
    def _build_query_text(input_payload: dict[str, Any], stage_state: dict[str, Any], stage: str) -> str:
        parts: list[str] = [
            str(input_payload.get("text", "") or ""),
            str(input_payload.get("topic_type", "") or ""),
            str(input_payload.get("lane", "") or ""),
            str(stage or ""),
        ]
        for key, value in stage_state.items():
            if key == "source_discovery":
                parts.append(str(value.get("web_note", "")))
            elif isinstance(value, dict):
                for field in ("reply", "evidence_summary", "open_risks"):
                    if field in value:
                        parts.append(str(value.get(field, "")))
        return " ".join(parts)

    @staticmethod
    def _build_retrieval_results(stage: str, stage_state: dict[str, Any]) -> dict[str, Any]:
        results: dict[str, Any] = {
            "stage": stage,
            "signals": {},
        }
        source_state = stage_state.get("source_discovery", {}) if isinstance(stage_state.get("source_discovery", {}), dict) else {}
        if source_state:
            results["signals"]["source_count"] = int(source_state.get("source_count", 0) or 0)
            note = str(source_state.get("web_note", "")).strip()
            if note:
                results["signals"]["web_note"] = note[:240]
        nuance_state = stage_state.get("nuance_pass", {}) if isinstance(stage_state.get("nuance_pass", {}), dict) else {}
        if nuance_state:
            risks = nuance_state.get("open_risks", [])
            if isinstance(risks, list) and risks:
                results["signals"]["open_risks"] = [str(x) for x in risks[:5]]
        return results

    @staticmethod
    def _recency_weight(row: dict[str, Any]) -> float:
        raw = str(row.get("updated_at", "")).strip() or str(row.get("created_at", "")).strip()
        if not raw:
            return 0.0
        try:
            when = datetime.fromisoformat(raw.replace("Z", "+00:00"))
            now = datetime.now(timezone.utc)
            delta_hours = max(0.0, (now - when).total_seconds() / 3600.0)
            # 0..1, where recent rows are favored
            return 1.0 / (1.0 + (delta_hours / 24.0))
        except Exception:
            return 0.0

    @staticmethod
    def _resolve_budget(hardware_token_budget: int | None) -> int:
        if hardware_token_budget is not None:
            return max(256, int(hardware_token_budget))
        env = str(os.getenv("OATHWEAVERX_MAX_STAGE_CONTEXT_TOKENS", "")).strip()
        if env:
            try:
                return max(256, int(env))
            except Exception:
                pass
        return 1800

    @staticmethod
    def _new_context_pack_id(stage: str) -> str:
        stamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        key = str(stage or "stage").strip().lower().replace(" ", "_")
        return f"ctx_{stamp}_{key}_{uuid.uuid4().hex[:8]}"
