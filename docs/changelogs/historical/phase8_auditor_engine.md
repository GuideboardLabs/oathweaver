# Phase 8 Auditor Engine

Phase 8 adds a typed Auditor loop that reads trace artifacts plus benchmark signals, proposes system changes, and can promote benchmark implications into CAG memory.

## Added modules

- `SourceCode/auditor/benchmark_import/`
  - Imports latest benchmark signals from repo-local results at `Runtime/benchmarks/cag_bench/results`.
  - Supports `runs.jsonl` when present, with fallback to `summary.csv` and `aggregated_metrics.csv`.

- `SourceCode/auditor/trace_analysis/`
  - Produces typed findings only from the approved set:
    - `wrong domain`
    - `wrong make type`
    - `wrong research focus`
    - `wrong specialist mix`
    - `wrong memory scope`
    - `missing topic knowledge`
    - `thread memory contradiction`
    - `project memory overfit`

- `SourceCode/auditor/implication_engine/`
  - Runs the auditor loop:
    - trace + replay + benchmark snapshot -> typed findings
    - typed findings -> proposed system changes
    - typed findings -> optional benchmark-implication promotion candidates

- `SourceCode/auditor/regression_reports/`
  - Writes per-run auditor reports under `Runtime/auditor/regression_reports/{run_id}/report.json`.

## Runtime wiring

`SourceCode/orchestrator/main.py` now:

1. Executes pipeline.
2. Builds trace stage rows and score.
3. Builds replay bundle payload.
4. Runs `AuditorEngine` for typed findings and proposals.
5. Optionally promotes auditor benchmark implications into CAG memory
   (`OATHWEAVERX_AUDITOR_PROMOTE_BENCHMARK_LESSONS`, default on).
6. Persists regression report.
7. Persists final trace and replay artifacts.
8. Updates capability registry observation.

## Notes

- Auditor findings are typed labels, not free-text.
- Benchmark importer is resilient to current cag-bench output shapes where `runs.jsonl` may be absent.
- Auditor promotion uses `benchmark_implication` memory rows with `status=benchmark-derived` and `human_status=unreviewed`.
