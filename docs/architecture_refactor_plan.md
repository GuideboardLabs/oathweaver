# Oathweaver Architecture Refactor Plan

This document captures the cohesive phase plan implemented in this package and the next recommended steps.

## Phase 1 — Completed in this ZIP

### Goals

- reduce startup weight
- isolate background-service boot logic
- create a clear landing zone for future service extraction
- improve repository polish and contributor ergonomics

### Changes made

- Added `SourceCode/web_gui/bootstrap.py` to own lazy singleton creation and background-service startup
- Added `SourceCode/orchestrator/services/turn_plan.py` and `turn_planner.py` for centralized turn-planning heuristics
- Added `SourceCode/orchestrator/services/infra_runtime.py` so heavyweight orchestrator helpers initialize lazily
- Updated `SourceCode/orchestrator/main.py` to use the new service layer
- Updated `SourceCode/web_gui/app.py` to delegate background service lifecycle to bootstrap helpers
- Rewrote `README.md` and added `CONTRIBUTING.md`, `LICENSE`, and `tools/repo_health_check.py`

## Phase 2 — Recommended next

- split `web_gui/app.py` into blueprints by route area
- extract legacy planning functionality from `shared_tools/legacy_planning_module.py` into a package
- define typed result models for research, make, and personal flows

## Phase 3 — Recommended after that

- unify routing logic behind a single `TurnPlan` execution path
- move mutable structured runtime state toward a stronger store boundary
- add focused unit tests around routing and persistence helpers

## Phase 4 — Longer-term

- background job model for long-running research flows
- progress streaming and richer activity tracing
- plugin-style lane registration

## External tools - Planning track (no runtime impact)

- Added planning-only roadmap for OpenClaw/CrewAI integration in `docs/external_tools_beginning_phases.md`.
- This track is intentionally isolated from active runtime behavior until contracts and guardrails are finalized.
