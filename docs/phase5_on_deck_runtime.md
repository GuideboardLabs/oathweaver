# Phase 5 On-Deck Runtime

Phase 5 adds deterministic on-deck scheduling so the next stage's cognitive package is pre-staged before execution proceeds.

## Added scheduler modules

- `SourceCode/scheduler/resource_budget/`
  - Hardware profile + budget manager for stage context limits and neural prefetch guardrails.
  - Default profile: `8gb_vram_16gb_ram`.

- `SourceCode/scheduler/specialist_registry/`
  - Stage-to-specialist manifest registry.
  - Manifest shape includes role prompt, output schema, CAG query profile, tool permissions, optional adapter, expected next role, and estimated tokens.

- `SourceCode/scheduler/bench_manager/`
  - Emits bench/cache tier snapshots (`vram_hot_seat`, `ram_on_deck`, `ram_warm`, `ssd_cold`) to `Runtime/scheduler/bench_events.jsonl`.

- `SourceCode/scheduler/on_deck_runtime/`
  - Deterministic planner that:
    - Always does Level-1 cognitive prefetch for next stage(s).
    - Optionally schedules Level-2 neural prefetch when budget allows and an adapter is present.
    - Produces cache hierarchy + prefetched context packs.

## Runtime integration

- `SourceCode/core/pipeline_engine/engine.py`
  - Added `on_deck_planner` callback.
  - Added prefetched context-pack cache so precompiled next-stage packs are reused when that stage executes.
  - Injects `on_deck_plan` into stage payload and includes `on_deck_plans` in final result.

- `SourceCode/core/state_store/store.py`
  - Stage events now include `on_deck_plan`.

- `SourceCode/orchestrator/main.py`
  - Initializes scheduler stack (`ResourceBudgetManager`, `SpecialistRegistry`, `BenchManager`, `OnDeckRuntime`).
  - Wires `_on_deck_planner` into pipeline execution.
  - Prefetches next-stage context packs through existing Context Compiler path.

## Behavioral outcome

- Deterministic pipelines now prepare the next stage while current stage runs.
- Level-1 prefetch is always active.
- Level-2 prefetch is budget-gated and adapter-gated.
- Scheduler snapshots are persisted for later replay/audit phases.
