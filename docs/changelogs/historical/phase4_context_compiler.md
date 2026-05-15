# Phase 4 Context Compiler

Phase 4 adds a first-class Context Compiler and Context Pack artifact system, then wires it into deterministic stage execution.

## Added core modules

- `SourceCode/core/context_pack/`
  - `schema.py`: canonical `ContextPack` object.
  - `store.py`: persistence under `Runtime/context_packs/`.
  - Every pack is persisted as a standalone JSON artifact plus indexed in `Runtime/context_packs/context_packs.jsonl`.

- `SourceCode/core/context_compiler/`
  - `profiles.py`: stage-to-specialist profile map so different stages get different context behavior.
  - `compiler.py`: token-budgeted context compilation using:
    - project kernel knowledge spine
    - validated CAG memory rows
    - decision ledger rows
    - benchmark lesson inputs
    - stage-specific output-contract reference

## Runtime wiring

- `SourceCode/core/pipeline_engine/engine.py`
  - Added `context_pack_builder` hook.
  - Before each stage executes, engine compiles/receives a stage context pack and injects it into stage payload as `context_pack`.
  - Context pack metadata is also returned in `result["context_packs"]`.

- `SourceCode/core/state_store/store.py`
  - Stage events now include `context_pack` so transient run state captures compiled context artifacts per stage.

- `SourceCode/orchestrator/main.py`
  - Initializes `ContextPackStore` and `ContextCompiler`.
  - Builds context packs per stage using current project kernel, validated memory rows, decision-ledger entries, and benchmark implications.
  - Uses `contract_for_stage(stage)` to stamp pack contract metadata.

## Phase requirements covered

- Context is expensive-by-default: stage packs are budgeted (`token_budget`, default `1800`, env override `OATHWEAVERX_MAX_STAGE_CONTEXT_TOKENS`).
- Role-scoped context: stage profile mapping assigns stage-specific specialist roles and memory preferences.
- Each stage receives a single compiled Context Pack artifact.
- Packs include inclusion/exclusion reasoning and never dump full raw memory indiscriminately.
- Packs are persisted for replay/benchmark/training-data use in later phases.
