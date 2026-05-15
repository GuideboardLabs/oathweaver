# Phase 1 Implementation (Hierarchy and Taxonomy)

Phase 1 installs the durable knowledge spine and execution spine surfaces.

## Knowledge spine

`Domain -> Topic -> Thread -> Project -> Run`

Implemented in:
- `SourceCode/core/project_kernel/schema.py`
- `SourceCode/core/project_kernel/store.py`
- `SourceCode/cag/scope.py`

The kernel store persists project kernels under:
- `Runtime/project_kernels/<project>.json`

Each kernel snapshot now includes:
- `knowledge_spine`
- `execution_spine`
- `current_scope`

## Execution spine

`Make Type -> Research Focus -> Pipeline -> Specialist Stages`

Implemented in:
- `SourceCode/taxonomy/make_types.py`
- `SourceCode/taxonomy/research_focus.py`
- `SourceCode/orchestrator/services/policy.py`
- `SourceCode/orchestrator/services/turn_plan.py`

Routing now emits:
- `domain`
- `make_type`
- `make_intent`
- `research_focus`
- `pipeline`

## Domain taxonomy

Implemented in:
- `SourceCode/taxonomy/domains.py`

Provides:
- canonical domain list
- topic-type to domain mapping
- domain normalization helpers

## Ported/adapted research policy files

Ported from the TUI fork and adapted for this repo:
- `SourceCode/agents_research/topic_policy.py`
- `SourceCode/agents_research/domain_primitives.py`

Active wiring:
- `deep_researcher._agent_specs(...)` now applies role-priority hints from `topic_policy`.
- `deep_researcher.run_research_pool(...)` now emits and persists domain primitives (`*.primitives.json`) when focus is applicable.

## Runtime integration points

- `OathweaverOrchestrator.plan_message(...)` now includes `project_kernel`.
- `set_project(...)` and `set_project_mode(...)` now initialize/update kernel state.
- Each routed turn updates the kernel via `ProjectKernelStore.update_for_turn(...)`.
- Research pool context now carries `domain`, `research_focus`, `make_type`, and `make_intent`.
