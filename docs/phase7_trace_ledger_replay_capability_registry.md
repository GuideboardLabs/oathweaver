# Phase 7 Trace Ledger, Replayability, Capability Registry

Phase 7 adds first-class run traces, deterministic replay bundles, and benchmark-backed capability claim tracking.

## Added modules

- `SourceCode/core/trace_ledger/`
  - Builds stage-level trace rows (`role`, `context_pack_id`, `cag_rows_used`, `tokens_in`, `tokens_out`, `latency_ms`, `output_score`).
  - Persists run traces under `Runtime/trace_ledger/{run_id}/trace.json` and indexes in `Runtime/trace_ledger/runs.jsonl`.

- `SourceCode/core/replay/`
  - Persists replay bundles under `Runtime/replay/{run_id}/bundle.json`.
  - Bundle includes model settings, input payload, context packs, stage outputs, stage audits, timings, hardware profile, promoted memory IDs, and timestamps.

- `SourceCode/core/capability_registry/`
  - Maintains capability claims in `Runtime/capability_registry/claims.json`.
  - Seeds default hypothesis claim for the 8B+CAG pipeline profile.
  - Records run observations keyed to claims.

## Runtime integration

- `SourceCode/core/pipeline_engine/engine.py`
  - Now returns:
    - `stage_audits`
    - `stage_timings_ms`
    - `started_at`
    - `finished_at`

- `SourceCode/orchestrator/main.py`
  - Initializes `TraceLedger`, `ReplayStore`, and `CapabilityRegistry`.
  - After each pipeline run, writes:
    1. trace ledger record,
    2. replay bundle,
    3. capability-registry run observation.

## Result shape

Each pipeline run now produces structured phase-7 artifacts suitable for:

- audit and regression analysis,
- deterministic replay/debugging,
- training-data extraction,
- capability claim evidence tracking.
