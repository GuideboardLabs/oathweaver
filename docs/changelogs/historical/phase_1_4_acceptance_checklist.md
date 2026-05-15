# Phase 1-4 Acceptance Checklist

This is the freeze gate for the memory, legacy planning-intelligence, behavior-eval, and second-brain UX work.

## Required checks

Run these before treating phases 1-4 as locked:

```bash
python tools/ui_phase_smoke.py
python tools/browser_headless_smoke.py
python -m unittest tests.test_db_connection_context tests.test_context_policy tests.test_second_brain_payload tests.test_gemini_cloud_consult tests.test_gemini_settings_route -v
python SourceCode/benchmark/context_usage_eval.py
python tools/gemini_live_check.py
python -m compileall tools SourceCode/shared_tools SourceCode/orchestrator SourceCode/web_gui tests
```

## Pass criteria

- Memory records can be created, pinned, explained, and surfaced through the ledger and second-brain APIs.
- Planner insights generate summary lines, suggestions, and actionable follow-up tasks.
- Context policy tests and evals pass without regressions.
- The Second Brain panel renders and the browser DOM contains the new phase 1/2/4 UI markers.
- Gemini settings routes work, Gemini claim-check logic passes locally, and the live Gemini check succeeds when a valid key and network access are available.
- SQLite connection warnings are absent from the targeted regression suite.

## Product-policy freeze

These behaviors are now baseline product policy unless intentionally changed:

- Personal memory is relevance-gated and should not surface weak context aggressively.
- Planner context should be synthesized before injection into normal chat.
- Context use should feel organic and restrained, not constant or self-congratulatory.
- The user must be able to inspect, edit, pin, or forget durable memory.
- Planner-derived transient items should not be promoted to long-term memory unless they are stable household facts.

## Operational notes

- `tools/ui_phase_smoke.py` is the fast app-level route and API smoke.
- `tools/browser_headless_smoke.py` is the real-browser headless check using a local Chrome/Edge binary if available.
- `tools/gemini_live_check.py` is intentionally small and should be used only for real integration verification, not unit coverage.
