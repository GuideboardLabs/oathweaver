# Phase 9 Watchtower Background Scout

Phase 9 inverts Watchtower from "briefing output" into a background knowledge scout that emits typed queued cards.

## Added modules

- `SourceCode/watchtower/knowledge_gap_detector/`
  - Converts auditor findings and benchmark signals into scoped gap proposals.

- `SourceCode/watchtower/research_cards/`
  - Persists proposal cards in `Runtime/watchtower/cards_state.json` plus event log `cards_events.jsonl`.
  - Card types: `research_card`, `knowledge_gap_card`, `benchmark_gap_card`, `capability_gap_card`.

- `SourceCode/watchtower/project_readiness/`
  - Produces a lightweight readiness assessment from kernel completeness and queued-card pressure.

- `SourceCode/watchtower/scout.py`
  - Orchestrates detector + card queue + readiness summary.

## Runtime behavior

- `SourceCode/shared_tools/watchtower.py`
  - Queues a `research_card` when a watch run generates a new briefing.
  - Exposes card APIs (`list_cards`, `get_card`, `set_card_status`).
  - Exposes `scan_project_gaps(...)`, which emits scoped queued gap cards.
  - Scans produce proposals only; they do not mutate CAG memory.

- `SourceCode/orchestrator/main.py`
  - After phase-8 auditor report persistence, optionally runs a phase-9 watchtower scan (`OATHWEAVERX_WATCHTOWER_SCAN_ENABLED`, default on).
  - Adds scan results to `details_sink["watchtower_scan"]`.

- `SourceCode/web_gui/routes/watchtower.py`
  - `POST /api/watchtower/scan`
  - `GET /api/watchtower/cards`
  - `GET /api/watchtower/cards/<card_id>`
  - `POST /api/watchtower/cards/<card_id>/status`

## Contract alignment

- Watchtower cards are explicit queued proposals.
- Supported decisions are status transitions (`queued`, `accepted`, `rejected`, `running`, `completed`).
- No silent CAG mutations occur in scan paths.
