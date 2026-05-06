from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class OutputContract:
    stage: str
    must_include: tuple[str, ...]
    must_not_include: tuple[str, ...]

    def as_dict(self) -> dict[str, Any]:
        return {
            "stage": self.stage,
            "must_include": list(self.must_include),
            "must_not_include": list(self.must_not_include),
        }


CONTRACTS: dict[str, OutputContract] = {
    # Research pipeline
    "intake": OutputContract("intake", ("question", "project"), ()),
    "domain_framing": OutputContract("domain_framing", ("domain", "topic", "thread"), ()),
    "source_discovery": OutputContract("source_discovery", ("web_context",), ("final_answer",)),
    "evidence_analysis": OutputContract("evidence_analysis", ("evidence_summary",), ("final_answer",)),
    "nuance_pass": OutputContract("nuance_pass", ("open_risks",), ("final_answer",)),
    "synthesis": OutputContract("synthesis", ("reply",), ("memory_promotion_decisions",)),
    "cag_promotion_gate": OutputContract("cag_promotion_gate", ("promotion_candidates",), ("new_unverified_claims",)),
    # Build pipeline
    "requirements": OutputContract("requirements", ("requirements",), ("patch", "final_answer")),
    "architecture": OutputContract("architecture", ("architecture_outline",), ("patch", "final_answer")),
    "implementation_plan": OutputContract("implementation_plan", ("implementation_plan",), ("patch", "final_answer")),
    "patch_artifact_generation": OutputContract("patch_artifact_generation", ("worker_result",), ()),
    "verification": OutputContract("verification", ("reply",), ("new_unverified_claims",)),
    # Code fix pipeline
    "planner": OutputContract("planner", ("plan",), ("patch", "final_answer")),
    "code_localizer": OutputContract("code_localizer", ("candidate_files",), ("patch", "final_answer")),
    "patch_writer": OutputContract("patch_writer", ("patch_text",), ("final_answer",)),
    "reviewer": OutputContract("reviewer", ("review_findings",), ("final_answer",)),
    "test_fixer": OutputContract("test_fixer", ("test_summary",), ("final_answer",)),
    "finalizer": OutputContract("finalizer", ("reply",), ("new_unverified_claims",)),
}


def contract_for_stage(stage: str) -> OutputContract:
    key = str(stage or "").strip()
    return CONTRACTS.get(key) or OutputContract(stage=key, must_include=tuple(), must_not_include=tuple())


def list_contracts() -> list[dict[str, Any]]:
    return [row.as_dict() for row in CONTRACTS.values()]
