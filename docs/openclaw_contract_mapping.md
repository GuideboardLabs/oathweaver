# OpenClaw Contract Mapping (Pre-Integration)

This maps OpenClaw concepts onto the provider-agnostic external request contract. No API wiring is included in this phase.

## Intent mapping

- `send_email`:
  - input payload: recipient, subject, body, priority
  - output: delivery status + message id
- `task_suggestion`:
  - input payload: context + suggested task metadata
  - output: suggestion list only (no auto-apply)
- `event_suggestion`:
  - input payload: context + date/time hints
  - output: suggestion list only (no auto-apply)

## Expected acknowledgement shape

Required OpenClaw ack fields to normalize:

- `external_ref` (provider-side request id)
- `status` (`acknowledged` or `working`)
- `message` (optional human-readable confirmation)

Normalization target in Oathweaver:

- store `external_ref` on the request row
- transition status to `acknowledged` (or `working`)
- emit audit event name based on transition

## Error mapping

- OpenClaw validation error -> `failed` + `result_json.error_type = "validation"`
- OpenClaw auth/config error -> `failed` + `result_json.error_type = "config"`
- OpenClaw timeout/network error -> keep non-terminal if retrying, else `failed` with `error_type = "timeout"`
- OpenClaw cancel signal -> `cancelled`

## Suggestions mapping

External suggestions are normalized to lightweight legacy planning suggestions:

- `type`: `task` or `event`
- `title`
- optional scheduling fields (`date`, `start_time`, `end_time`)
- `confidence`
- `source = "openclaw"`

Suggestions are surfaced in Postbag/legacy planning suggestion UI only. No automatic task or event insertion.
