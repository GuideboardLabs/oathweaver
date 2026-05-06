# Phase 3 CAG Core

This phase turns CAG memory into a first-class subsystem and wires it into the deterministic `research_pipeline` stage `cag_promotion_gate`.

## Added subsystems

- `SourceCode/cag/memory_store/`
  - Hybrid store: SQLite (`Runtime/cag/memory_rows.sqlite3`) + JSONL event log (`Runtime/cag/memory_rows.jsonl`)
  - Row fields include: `scope`, `type`, `status`, `evidence`, `supersedes`, `superseded_by`, `confidence`, `human_status`
  - Includes lifecycle-safe row updates and supersession links

- `SourceCode/cag/selector/`
  - `ScopedSelector.retrieve_scoped(...)` aligned with cag-bench weighting:
    - `3.0 * concept_overlap`
    - `1.0 * tag_overlap`
    - `0.5 * task_text_overlap`
    - `1.0 * recency_weight`
  - Returns selectable rows and optional score breakdowns

- `SourceCode/cag/promotion_gate/`
  - Enforces durable-memory criteria:
    - promotable type
    - compact text
    - scope and tags present
    - validation signal present
    - non-redundant
    - contradiction guardrails + contradiction budget

- `SourceCode/cag/lifecycle/`
  - Lifecycle state set:
    - `candidate | accepted | superseded | deprecated | expired | benchmark-derived | watchtower-derived | user-confirmed`
  - Human status set:
    - `unreviewed | accepted | rejected`
  - Transition checker utility

- `SourceCode/cag/contradiction_detector/`
  - Detects candidate vs existing conflict labels:
    - `error | intentional revision | scope mismatch | outdated memory | ambiguous terminology`
  - Exposes contradiction-budget accounting for non-error contradictions

- `SourceCode/cag/decision_ledger/`
  - First-class queryable decision ledger with SQLite + JSONL event log
  - Tracks accepted decision-like memory rows (`decision`, `constraint`, `lesson`, `benchmark_implication`)

## Orchestrator integration

`SourceCode/orchestrator/main.py` now:

- Instantiates CAG core services in `OathweaverOrchestrator.__init__`
- Replaces the `cag_promotion_gate` placeholder with full flow:
  1. Build candidate memory row from synthesis output + current scope
  2. Retrieve scoped prior rows via selector
  3. Detect contradictions
  4. Evaluate promotion gate with contradiction budget
  5. Persist accepted rows
  6. Apply supersession links
  7. Append decision ledger entries

Stage output now carries:

- `promotion_candidates`
- `accepted_memory_ids`
- `rejected_reasons`
- `contradictions`
- `contradiction_budget`
- `selector_scores`
- `decision_ledger_entries`

## Tests

- `tests/test_phase3_cag_core.py`
  - Memory store + supersession behavior
  - Selector weighting and ranking
  - Contradiction detection + budget
  - Promotion gate acceptance behavior
  - Decision ledger tracking
