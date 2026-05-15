# OpenClaw Readiness Handoff Checklist

Use this checklist when starting real provider wiring after this phase.

## Preconditions

- `external_tools.mode` defaults to `off` and is respected as a hard stop.
- External request contract and state transitions are frozen.
- Pending actions can serialize `external_request` rows without breaking existing item types.
- No auto-apply legacy planning behavior exists for external suggestions.

## First implementation steps (next phase)

1. Create `OpenClawAdapter` implementing `ExternalProviderAdapter`.
2. Wire adapter registration without changing default mode (`off`).
3. Implement `submit` path:
   - create `external_request` row (`queued`)
   - dispatch to OpenClaw
   - persist `external_ref`
   - transition to `acknowledged` or `working`
4. Implement polling/status hydration:
   - normalize provider status
   - update store transition
   - append result/suggestions
5. Add adapter integration tests with mocked OpenClaw responses.

## Out-of-scope guardrails (must stay off in readiness phase)

- no live OpenClaw API requests
- no webhooks
- no background worker activation for provider polling
- no automatic legacy planning mutations from external output
