from __future__ import annotations

from typing import Any


FINDING_TYPES: tuple[str, ...] = (
    "wrong domain",
    "wrong make type",
    "wrong research focus",
    "wrong specialist mix",
    "wrong memory scope",
    "missing topic knowledge",
    "thread memory contradiction",
    "project memory overfit",
)


class TraceAnalyzer:
    """Interprets run traces into typed auditor findings."""

    def analyze(
        self,
        *,
        trace_row: dict[str, Any],
        replay_row: dict[str, Any],
        benchmark_snapshot: dict[str, Any],
        project_kernel: dict[str, Any],
    ) -> list[dict[str, Any]]:
        findings: list[dict[str, Any]] = []
        stages = trace_row.get("stages", []) if isinstance(trace_row.get("stages", []), list) else []
        stage_roles = [str(x.get("role", "")).strip() for x in stages if isinstance(x, dict)]

        knowledge = project_kernel.get("knowledge_spine", {}) if isinstance(project_kernel.get("knowledge_spine", {}), dict) else {}
        execution = project_kernel.get("execution_spine", {}) if isinstance(project_kernel.get("execution_spine", {}), dict) else {}
        kernel_domain = str(knowledge.get("domain", "")).strip().lower()
        kernel_topic = str(knowledge.get("topic", "")).strip().lower()
        make_type = str(execution.get("make_type", "")).strip().lower()
        research_focus = str(execution.get("research_focus", "")).strip().lower()

        replay_input = replay_row.get("input_payload", {}) if isinstance(replay_row.get("input_payload", {}), dict) else {}
        input_topic = str(replay_input.get("topic_type", "")).strip().lower()
        input_target = str(replay_input.get("target", "")).strip().lower()
        input_query_mode = str(replay_input.get("query_mode", "")).strip().lower()

        # Wrong domain/type/focus consistency checks.
        if kernel_domain and input_topic and kernel_domain != input_topic and kernel_domain not in input_topic:
            findings.append(self._finding("wrong domain", "medium", "kernel_domain_input_topic_mismatch"))

        if input_target and make_type and input_target != make_type and input_target not in make_type:
            findings.append(self._finding("wrong make type", "medium", "execution_make_type_input_target_mismatch"))

        if input_query_mode and research_focus and input_query_mode != research_focus and input_query_mode not in research_focus:
            findings.append(self._finding("wrong research focus", "low", "execution_focus_input_query_mode_mismatch"))

        # Specialist mix heuristics by pipeline.
        pipeline = str(trace_row.get("pipeline", "")).strip().lower()
        required_roles = {
            "research_pipeline": {"researcher", "synthesizer", "memory_critic"},
            "build_pipeline": {"planner", "verifier"},
            "code_fix_pipeline": {"planner", "verifier"},
        }.get(pipeline, set())
        if required_roles:
            normalized_roles = {self._normalize_role(r) for r in stage_roles if r}
            if not required_roles.issubset(normalized_roles):
                findings.append(self._finding("wrong specialist mix", "medium", "required_specialist_roles_missing"))

        # Memory scope + contradiction checks.
        total_memory_rows = 0
        contradiction_hits = 0
        for stage in stages:
            if not isinstance(stage, dict):
                continue
            used = stage.get("cag_rows_used", []) if isinstance(stage.get("cag_rows_used", []), list) else []
            total_memory_rows += len(used)
            audit = stage.get("contract_audit", {}) if isinstance(stage.get("contract_audit", {}), dict) else {}
            if not bool(audit.get("ok", True)):
                contradiction_hits += 1

        signals = benchmark_snapshot.get("signals", {}) if isinstance(benchmark_snapshot.get("signals", {}), dict) else {}
        high_memory_low_continuity = bool(signals.get("high_memory_low_continuity", False))
        high_memory_low_score = bool(signals.get("high_memory_low_score", False))

        if high_memory_low_continuity or (total_memory_rows > 8 and contradiction_hits > 0):
            findings.append(self._finding("wrong memory scope", "high", "memory_usage_not_improving_continuity"))

        if high_memory_low_score:
            findings.append(self._finding("project memory overfit", "high", "high_memory_usage_with_low_score"))

        # Topic knowledge checks.
        continuity = float(signals.get("continuity_recall", 0.0) or 0.0)
        score = float(signals.get("score", 0.0) or 0.0)
        if continuity < 40.0 and score < 50.0:
            findings.append(self._finding("missing topic knowledge", "high", "low_continuity_and_score"))

        # Thread contradiction checks from trace stage output.
        stage_outputs = replay_row.get("stage_outputs", {}) if isinstance(replay_row.get("stage_outputs", {}), dict) else {}
        gate = stage_outputs.get("cag_promotion_gate", {}) if isinstance(stage_outputs.get("cag_promotion_gate", {}), dict) else {}
        contradictions = gate.get("contradictions", []) if isinstance(gate.get("contradictions", []), list) else []
        has_error_contradiction = any(str(x.get("label", "")).strip().lower() == "error" for x in contradictions if isinstance(x, dict))
        if has_error_contradiction:
            findings.append(self._finding("thread memory contradiction", "high", "promotion_gate_error_contradiction"))

        # de-dupe by type keep highest severity
        deduped: dict[str, dict[str, Any]] = {}
        severity_rank = {"high": 3, "medium": 2, "low": 1}
        for row in findings:
            ftype = str(row.get("type", "")).strip()
            existing = deduped.get(ftype)
            if existing is None or severity_rank.get(str(row.get("severity", "low")), 1) > severity_rank.get(str(existing.get("severity", "low")), 1):
                deduped[ftype] = dict(row)
        return list(deduped.values())

    @staticmethod
    def _normalize_role(role: str) -> str:
        key = str(role or "").strip().lower()
        alias = {
            "runtime_architect": "planner",
            "memory_systems_analyst": "memory_critic",
            "benchmark_designer": "auditor",
            "code_reviewer": "verifier",
            "systems_skeptic": "skeptic",
        }
        return alias.get(key, key)

    @staticmethod
    def _finding(ftype: str, severity: str, evidence: str) -> dict[str, Any]:
        if ftype not in FINDING_TYPES:
            ftype = "wrong specialist mix"
        sev = str(severity or "low").strip().lower()
        if sev not in {"low", "medium", "high"}:
            sev = "low"
        return {
            "type": ftype,
            "severity": sev,
            "evidence": evidence,
        }
