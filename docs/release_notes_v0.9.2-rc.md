# Oathweaver Release Notes — v0.9.2-rc

## Summary

`v0.9.2-rc` focuses on hardening and operator visibility ahead of 1.0: stronger local-default security, pass-3 performance updates for memory persistence, and better runtime self-awareness of model/backends/hardware behavior.

## Highlights

### Security hardening

- OpenAI-compatible API now enforces bearer-token auth for non-loopback requests.
- Approval gate defaults to enabled (`OATHWEAVER_APPROVAL_GATE=1`).
- Session cookie policy tightened (`SameSite=Strict`, HTTPS-aware secure-cookie behavior).
- Web GUI and Ollama loopback defaults reinforced.
- Semantic gate persistence migrated from pickle to JSON.
- Migration table identifiers constrained via allowlist checks.
- Owner API redacts SMTP-user values.
- Legacy `Archive/web_gui_legacy_*` surfaces removed.

### Runtime diagnostics and self-awareness

- Inference router gained stronger diagnostics (`health_report`, backend reachability, fallback chain, memory-state, route explanation).
- Hardware profiles are now first-class runtime policy input and validation context.
- Tier A self-awareness lane injects live runtime facts for self-query responses.

### Performance and reliability

- CAG SQLite stores moved to WAL + `synchronous=NORMAL` defaults.
- CI now runs Python 3.10 and 3.12 on push/PR.

## Operator notes

- Token file lives at `Runtime/state/api_token`; protect host-level access accordingly.
- If you expose LAN/WAN manually, maintain your own perimeter controls; defaults remain local-first.
- See `CHANGELOG.md` for full historical delta context and `RELEASE_PROCESS.md` for cut criteria.
