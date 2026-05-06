# Phase 2 Implementation (Core Kernel + Pipeline Engine + Output Contracts)

Phase 2 introduces deterministic pipeline execution around the Project Kernel.

## New core modules

- `SourceCode/core/pipeline_engine/`
  - deterministic stage sequencer
  - pipeline specs: `research_pipeline`, `build_pipeline`, `code_fix_pipeline`
- `SourceCode/core/output_contracts/`
  - per-stage output contracts (`must_include`, `must_not_include`)
  - contract auditor
- `SourceCode/core/state_store/`
  - transient run-state persistence (`Runtime/state/pipeline_state.jsonl`)

## Runtime wiring

- `SourceCode/orchestrator/main.py`
  - orchestrator now instantiates:
    - `StateStore`
    - `OutputContractAuditor`
    - `PipelineEngine`
  - turn handling now routes eligible lanes through `_execute_pipeline_turn(...)`
  - stage outputs are audited and persisted per run
  - Project Kernel is updated per turn and attached to planning/details payloads

## Deterministic pipeline behavior

- `research_pipeline` stages:
  - `intake -> domain_framing -> source_discovery -> evidence_analysis -> nuance_pass -> synthesis -> cag_promotion_gate`
- `build_pipeline` stages:
  - `requirements -> architecture -> implementation_plan -> patch_artifact_generation -> verification`
- `code_fix_pipeline` stages:
  - `planner -> code_localizer -> patch_writer -> reviewer -> test_fixer -> finalizer`

## State vs memory enforcement (Phase 2 baseline)

- pipeline stage data writes to transient `StateStore`
- legacy project-fact memory writes during turn intake are now opt-in only:
  - `OATHWEAVERX_ENABLE_LEGACY_MEMORY_WRITES=1`

This keeps default execution state-first while preserving a migration escape hatch.
