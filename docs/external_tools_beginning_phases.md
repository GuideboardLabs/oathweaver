# External Tools Beginning Phases (Planning Only)

This plan defines the first external-tool phases without changing current runtime behavior.

## Scope and constraints

- No new runtime dependencies.
- No orchestrator routing changes in active paths.
- No network calls to external providers.
- No automatic task/event insertion from external outputs.
- All work in this document is planning, contracts, and test strategy only.

## Why now

Oathweaver already has the right primitives for safe expansion later:

- pending-request style flow in `CloudConsultEngine`
- proposal/approval model for user-visible actions
- legacy planning suggestion panels and manual apply UX

The next step is to formalize external-tool contracts so OpenClaw and CrewAI can plug in cleanly.

## Cluster A: Platform contract (Phase E1-E2)

### Phase E1 - External request contract and lifecycle

Goal: define one reusable request envelope for all providers.

Deliverables (design artifacts only):

- request envelope schema
- status lifecycle spec
- idempotency and dedupe rules
- event taxonomy for observability

Core request envelope (target shape):

```json
{
  "request_id": "ext_abc123",
  "provider": "openclaw",
  "project": "general",
  "lane": "project",
  "intent": "send_email",
  "summary": "Send update email to school contact",
  "payload": {},
  "origin": {
    "source": "oathweaver_orchestrator",
    "user_id": "owner",
    "conversation_id": "..."
  },
  "policy": {
    "requires_user_approval": true,
    "auto_apply_planner": false
  },
  "created_at": "2026-03-13T00:00:00Z"
}
```

Lifecycle states (proposed):

`queued -> dispatched -> acknowledged -> working -> completed | failed | cancelled`

Exit criteria:

- schema accepted
- lifecycle states finalized
- replay/idempotency strategy documented

### Phase E2 - Provider adapter interface

Goal: define one adapter interface so each provider is a thin plugin.

Interface (design contract):

- `validate_config() -> ValidationResult`
- `submit(request) -> ProviderAck`
- `poll_status(request_id) -> ProviderStatus`
- `normalize_result(raw) -> ExternalResult`
- `map_suggestions(result) -> PlannerSuggestion[]`

Guardrails:

- adapter failures return normalized errors
- no provider-specific payloads escape adapter boundary
- retries and backoff policy defined centrally, not per adapter

Exit criteria:

- adapter API reviewed
- error classes and retry classes documented
- compatibility matrix drafted for OpenClaw and CrewAI

## Cluster B: OpenClaw pilot design (Phase E3)

### Phase E3 - OpenClaw flow specification (no runtime wiring)

Goal: define exact Oathweaver <-> OpenClaw interaction semantics.

Planned behaviors:

- Oathweaver creates an external request with intent (example: `send_email`).
- OpenClaw immediately acknowledges receipt with request metadata.
- OpenClaw can emit:
  - completion/failure status
  - legacy planning suggestions (tasks/events only as suggestions)
- Oathweaver surfaces suggestions in panel with quick-apply.
- Nothing is auto-applied.

Required message types:

- `request_ack`
- `request_progress`
- `request_completed`
- `request_failed`
- `legacy_planning_suggestions`

OpenClaw-specific acceptance gates:

- ack received within timeout budget
- status polling/backoff policy defined
- malformed callback handling defined

## Cluster C: CrewAI onboarding design (Phase E4)

### Phase E4 - CrewAI workstream model

Goal: reuse the same contract for dev-task offload workflows.

Planned intents:

- `code_research`
- `implementation_plan`
- `test_plan`
- `artifact_generation`

Outputs expected:

- result summary
- artifact links/paths
- optional legacy planning suggestions

Constraint:

- CrewAI output remains suggestion-first and approval-gated.

## Cross-cutting requirements

- Security: per-provider API key isolation, request signing, callback verification.
- Privacy: redact sensitive personal data by policy before dispatch.
- Audit: log every state transition with timestamp and actor.
- UX: always show provider status and confidence, never silently fail.

## Implementation trigger checklist (before any code wiring)

1. Schema and lifecycle are frozen.
2. Provider adapter interface is frozen.
3. Failure-mode table is complete (timeouts, retries, bad payload, duplicate callbacks).
4. Suggestion UX copy and apply/ignore semantics are approved.
5. Rollback switch is defined (`external_tools.mode = off` hard stop).

## Out of scope in this phase set

- live provider API calls
- background workers
- webhook listeners
- legacy planning auto-apply
- autonomous chained execution

## Readiness artifacts produced

- `docs/external_requests_migration_spec.md`
- `docs/openclaw_contract_mapping.md`
- `docs/openclaw_readiness_handoff_checklist.md`
