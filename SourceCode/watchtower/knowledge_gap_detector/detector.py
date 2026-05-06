from __future__ import annotations

from typing import Any


class KnowledgeGapDetector:
    """Converts auditor + benchmark signals into scoped watchtower card proposals."""

    def detect(
        self,
        *,
        project: str,
        project_kernel: dict[str, Any],
        auditor_report: dict[str, Any],
        capability_claims: list[dict[str, Any]] | None = None,
    ) -> list[dict[str, Any]]:
        scope = self._scope_from_kernel(project_kernel, project=project)
        typed_findings = [
            str(x.get("type", "")).strip().lower()
            for x in auditor_report.get("typed_findings", [])
            if isinstance(x, dict)
        ]
        benchmark_snapshot = auditor_report.get("benchmark_snapshot", {}) if isinstance(auditor_report.get("benchmark_snapshot", {}), dict) else {}
        signals = benchmark_snapshot.get("signals", {}) if isinstance(benchmark_snapshot.get("signals", {}), dict) else {}
        proposals: list[dict[str, Any]] = []

        if any(x in typed_findings for x in {"missing topic knowledge", "wrong domain", "wrong research focus"}):
            proposals.append(
                {
                    "card_type": "knowledge_gap_card",
                    "scope_level": "topic",
                    "scope": dict(scope),
                    "title": "Topic knowledge gap detected",
                    "summary": "Auditor found missing or misaligned topic knowledge; gather durable domain sources before the next run.",
                    "recommended_action": "Queue targeted source-discovery pass and promote only validated topic facts.",
                    "priority": "high",
                    "evidence": [
                        {
                            "kind": "typed_findings",
                            "value": [x for x in typed_findings if x in {"missing topic knowledge", "wrong domain", "wrong research focus"}],
                        }
                    ],
                    "source": "watchtower.knowledge_gap_detector",
                    "linked_run_id": str(auditor_report.get("run_id", "")).strip(),
                }
            )

        if any(x in typed_findings for x in {"wrong memory scope", "project memory overfit"}) or bool(signals.get("high_memory_low_continuity", False)):
            proposals.append(
                {
                    "card_type": "benchmark_gap_card",
                    "scope_level": "thread",
                    "scope": dict(scope),
                    "title": "Benchmark memory-scope gap",
                    "summary": "Benchmark signals suggest memory retrieval is broad or stale relative to continuity gains.",
                    "recommended_action": "Tighten context compiler memory scope and validate with next cag-bench pass.",
                    "priority": "high",
                    "evidence": [
                        {
                            "kind": "benchmark_signals",
                            "value": {
                                "continuity_recall": float(signals.get("continuity_recall", 0.0) or 0.0),
                                "memory_usage_rate": float(signals.get("memory_usage_rate", 0.0) or 0.0),
                                "high_memory_low_continuity": bool(signals.get("high_memory_low_continuity", False)),
                                "high_memory_low_score": bool(signals.get("high_memory_low_score", False)),
                            },
                        }
                    ],
                    "source": "watchtower.knowledge_gap_detector",
                    "linked_run_id": str(auditor_report.get("run_id", "")).strip(),
                }
            )

        if "wrong specialist mix" in typed_findings:
            proposals.append(
                {
                    "card_type": "capability_gap_card",
                    "scope_level": "project",
                    "scope": dict(scope),
                    "title": "Specialist capability mix gap",
                    "summary": "Auditor flagged specialist-role coverage mismatch for this pipeline stage mix.",
                    "recommended_action": "Adjust specialist derivation and schedule manifests before next long run.",
                    "priority": "medium",
                    "evidence": [{"kind": "typed_findings", "value": ["wrong specialist mix"]}],
                    "source": "watchtower.knowledge_gap_detector",
                    "linked_run_id": str(auditor_report.get("run_id", "")).strip(),
                }
            )

        claims = [dict(x) for x in (capability_claims or []) if isinstance(x, dict)]
        weak_claim = self._weak_capability_claim(claims)
        if weak_claim:
            proposals.append(
                {
                    "card_type": "capability_gap_card",
                    "scope_level": "project",
                    "scope": dict(scope),
                    "title": "Capability claim confidence gap",
                    "summary": f"Capability claim remains at risk: {weak_claim}",
                    "recommended_action": "Run focused benchmark and collect stronger evidence before marking stable.",
                    "priority": "medium",
                    "evidence": [{"kind": "capability_claim", "value": weak_claim}],
                    "source": "watchtower.knowledge_gap_detector",
                    "linked_run_id": str(auditor_report.get("run_id", "")).strip(),
                }
            )

        return self._dedupe(proposals)

    @staticmethod
    def _scope_from_kernel(project_kernel: dict[str, Any], *, project: str) -> dict[str, str]:
        current = project_kernel.get("current_scope", {}) if isinstance(project_kernel.get("current_scope", {}), dict) else {}
        knowledge = project_kernel.get("knowledge_spine", {}) if isinstance(project_kernel.get("knowledge_spine", {}), dict) else {}
        return {
            "domain": str(current.get("domain", knowledge.get("domain", ""))).strip(),
            "topic": str(current.get("topic", knowledge.get("topic", ""))).strip(),
            "thread": str(current.get("thread", knowledge.get("thread", ""))).strip(),
            "project": str(current.get("project", knowledge.get("project", project))).strip() or str(project),
            "run": str(current.get("run", knowledge.get("run", ""))).strip(),
        }

    @staticmethod
    def _weak_capability_claim(claims: list[dict[str, Any]]) -> str:
        for row in claims:
            status = str(row.get("status", "")).strip().lower()
            observations = row.get("observations", []) if isinstance(row.get("observations", []), list) else []
            low_score = False
            if observations:
                scores = [float(x.get("final_score", 0.0) or 0.0) for x in observations if isinstance(x, dict)]
                if scores:
                    avg = sum(scores) / max(1, len(scores))
                    low_score = avg < 0.6
            if status in {"hypothesis", "at_risk"} or low_score:
                return str(row.get("claim", "")).strip()
        return ""

    @staticmethod
    def _dedupe(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
        seen: set[tuple[str, str]] = set()
        out: list[dict[str, Any]] = []
        for row in rows:
            card_type = str(row.get("card_type", "")).strip().lower()
            title = str(row.get("title", "")).strip().lower()
            key = (card_type, title)
            if key in seen:
                continue
            seen.add(key)
            out.append(dict(row))
        return out
