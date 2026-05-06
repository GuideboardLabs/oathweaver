from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class StageContextProfile:
    specialist_role: str
    preferred_memory_types: tuple[str, ...] = field(default_factory=tuple)
    preferred_scope_levels: tuple[str, ...] = field(default_factory=tuple)
    include_decision_ledger: bool = True


_STAGE_PROFILES: dict[str, StageContextProfile] = {
    # research pipeline
    "intake": StageContextProfile("intake_analyst", ("constraint", "decision", "fact"), ("project", "thread", "topic")),
    "domain_framing": StageContextProfile("domain_framer", ("fact", "decision", "constraint"), ("domain", "topic", "thread")),
    "source_discovery": StageContextProfile("research_discovery", ("fact", "benchmark_implication", "lesson"), ("topic", "thread", "project")),
    "evidence_analysis": StageContextProfile("evidence_analyst", ("fact", "benchmark_implication", "decision"), ("topic", "thread", "project")),
    "nuance_pass": StageContextProfile("nuance_skeptic", ("lesson", "benchmark_implication", "constraint"), ("thread", "project", "topic")),
    "synthesis": StageContextProfile("synthesizer", ("decision", "constraint", "lesson", "fact"), ("thread", "project", "topic")),
    "cag_promotion_gate": StageContextProfile("memory_critic", ("decision", "constraint", "lesson", "benchmark_implication"), ("thread", "project", "topic")),
    # build pipeline
    "requirements": StageContextProfile("requirements_planner", ("constraint", "decision", "fact"), ("project", "thread", "topic")),
    "architecture": StageContextProfile("runtime_architect", ("decision", "constraint", "lesson"), ("thread", "project", "topic")),
    "implementation_plan": StageContextProfile("implementation_planner", ("decision", "lesson", "constraint"), ("project", "thread", "topic")),
    "patch_artifact_generation": StageContextProfile("patch_writer", ("decision", "constraint", "fact"), ("project", "thread", "topic")),
    "verification": StageContextProfile("verifier", ("benchmark_implication", "lesson", "constraint"), ("thread", "project", "topic")),
    # code-fix pipeline
    "planner": StageContextProfile("code_planner", ("decision", "constraint", "fact"), ("project", "thread", "topic")),
    "code_localizer": StageContextProfile("code_localizer", ("decision", "constraint", "fact"), ("project", "thread", "topic")),
    "patch_writer": StageContextProfile("patch_writer", ("decision", "constraint", "lesson"), ("project", "thread", "topic")),
    "reviewer": StageContextProfile("reviewer", ("lesson", "constraint", "benchmark_implication"), ("thread", "project", "topic")),
    "test_fixer": StageContextProfile("test_fixer", ("lesson", "constraint", "benchmark_implication"), ("project", "thread", "topic")),
    "finalizer": StageContextProfile("finalizer", ("decision", "lesson", "benchmark_implication"), ("thread", "project", "topic")),
}


_DEFAULT_PROFILE = StageContextProfile(
    specialist_role="general_specialist",
    preferred_memory_types=("decision", "constraint", "fact", "lesson", "benchmark_implication"),
    preferred_scope_levels=("project", "thread", "topic", "domain"),
    include_decision_ledger=True,
)


def profile_for_stage(stage: str) -> StageContextProfile:
    return _STAGE_PROFILES.get(str(stage or "").strip(), _DEFAULT_PROFILE)
