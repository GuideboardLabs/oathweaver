# Security Policy

## Reporting a Vulnerability

Please report security issues through a private GitHub Security Advisory for this repository.

If you cannot use GitHub advisories, open a minimal issue requesting a private security contact path and do not include exploit details in the public issue.

## Response Targets

- Initial acknowledgement: within 2 business days
- Triage decision (accepted / needs more info / out of scope): within 5 business days
- Status updates for accepted issues: at least every 7 calendar days until resolution

## Scope

In scope:
- Authentication and authorization bypasses
- Token/secret exposure or unsafe secret storage
- Privilege escalation or unintended command execution
- Defaults that expose local-only surfaces beyond loopback
- Integrity issues in approval gating or migration safety checks

Out of scope unless caused by shipped defaults:
- User-introduced LAN/WAN exposure from manual reverse-proxy or firewall changes
- Vulnerabilities in unsupported forks or heavily modified local deployments
- Social engineering, phishing, or physical access attacks

## Security Defaults (Current)

- Web GUI and Ollama default to loopback binds
- OpenAI-compatible API uses bearer-token auth for non-loopback paths
- Approval gate defaults to on (`OATHWEAVER_APPROVAL_GATE=1`)
- Session cookies use `SameSite=Strict`
- Secret material should be written via `SourceCode/shared_tools/secret_files.py`
