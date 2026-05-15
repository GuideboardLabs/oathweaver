# Phase 12 cag-bench First-Class Loop

Phase 12 adds native benchmark integration so Oathweaver can be evaluated continuously from repo-local benchmark artifacts under `Runtime/benchmarks/cag_bench/results` rather than treating benchmarking as an external side task.

## Added modules

- `SourceCode/benchmarks/cag_bench_adapter/adapter.py`
  - `CagBenchMemoryAdapter` bridges Oathweaver `CAGMemoryStore` rows to cag-bench-style memory rows.
  - Supports `import_rows`, `export_rows`, and `retrieve_scoped` using the existing scoped selector.
  - Exposes `as_backend()` call surface for benchmark harness integration.

- `SourceCode/benchmarks/cag_bench_adapter/workflow_benchmark.py`
  - `WorkflowBenchmarkEvaluator` computes phase-12 workflow comparisons:
    - `8b_one_shot`
    - `8b_rag`
    - `8b_cag`
    - `8b_oathweaver_multi_agent_no_cag`
    - `8b_oathweaver_plus_cag`
    - `70b_one_shot`
  - Includes ship-gate check: `8b_oathweaver_plus_cag` must win or tie `cag_scoped_promptonly`.
  - Includes budget gate against hardware profile token ceilings.

- `SourceCode/benchmarks/hardware_profiles/profiles.py`
  - Declares constrained profile `8gb_vram_16gb_ram`:
    - `max_context_tokens=4096`
    - `max_parallel_models=1`
    - `on_deck_depth=1`
    - `warm_depth=1`
    - `max_stage_context_tokens=1800`

## Runtime wiring

- `SourceCode/core/kernel_commands/service.py`
  - Added benchmark-first-class kernel commands:
    - `benchmark_backend_export(...)`
    - `benchmark_workflow_eval(...)`
    - `apply_hardware_profile(...)`
  - `pipeline_run(...)` now accepts optional `hardware_profile` and applies it to scheduler budget manager.

- `SourceCode/orchestrator/main.py`
  - Pipeline payload now includes:
    - `hardware_token_budget`
    - `hardware_profile`
  - Context Compiler receives profile-aligned token budget through existing context-pack flow.

- Interface exposure:
  - CLI: `benchmark-backend-export`, `benchmark-workflow-eval`
  - TUI: `/bench-export`, `/bench-workflow`
  - API: `/v1/kernel/benchmark/backend-export`, `/v1/kernel/benchmark/workflow-eval`

## Outcome

This phase provides the adapter and evaluation loop needed for direct cag-bench-aligned benchmarking, with hardware-budget-aware gating and command-level integration across unified interfaces.
