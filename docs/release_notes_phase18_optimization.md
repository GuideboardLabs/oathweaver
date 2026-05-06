# Oathweaver Release Notes — Phase 18 Optimization Pass

This release focuses on adaptive performance improvements that reduce unnecessary work while preserving accuracy.

## Included components
- Adaptive query routing (`query_router.py`)
- Lightweight performance tracing (`perf_trace.py`)
- Local summary retrieval helper (`embedding_memory.py`)
- Diversity-aware early stopping and page caching in `web_research.py`
- Confidence gate in `answer_composer.py`
- Light research path in `orchestrator/main.py`
- Cloud consult migration cleanup in `cloud_consult.py`

## Primary benefits
- Faster simple factual and live-event responses
- Less over-foraging on low-complexity questions
- Better reuse of prior local summaries
- Better observability via perf traces

## New runtime artifacts
- `Runtime/logs/perf_trace.jsonl`

## Recommended validation checklist
1. Run a simple factual sports query and confirm it takes the light path.
2. Run a deeper compare/analyze research prompt and confirm full foraging still runs.
3. Check `Runtime/logs/perf_trace.jsonl` for timings.
4. Confirm `web_research.py` returns earlier when quality/diversity thresholds are met.
5. Verify no more `runs_log_path` failures from cloud consult logging.
