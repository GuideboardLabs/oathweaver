# Changelog

All notable changes to this project are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project follows [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added
- Release-process docs for `SECURITY.md`, `RELEASE_PROCESS.md`, and `UPGRADE_GUIDE.md`.
- Historical-doc archive under `docs/changelogs/historical/`.

### Changed
- Installer defaults now pin Ollama installer script source and checksum by default.
- Packaging scripts now read `VERSION` and emit versioned artifact names.

## [0.9.2-rc] - 2026-05-14

### Added
- Inference-router diagnostics surface (`health_report`, fallback chain explanations, backend reachability/memory-state inspection).
- Hardware-profile runtime policy and validation surfaces.
- Tier A self-awareness layer for live configuration introspection responses.
- OpenAI-compatible API bearer-token auth with on-disk token generation (`Runtime/state/api_token`).

### Changed
- Web GUI and Ollama defaults tightened to loopback binds (`127.0.0.1`).
- Session cookie policy hardened with `SameSite=Strict` and HTTPS-aware secure-cookie behavior.
- CAG SQLite stores now use WAL and `synchronous=NORMAL` defaults.
- CI runs on Python 3.10 and 3.12 for push/PR coverage.

### Security
- Approval gate default-on behavior (`OATHWEAVER_APPROVAL_GATE=1`).
- Semantic gate persistence moved from pickle to JSON.
- Migration table-identifier allowlisting and owner API SMTP-user redaction hardening.
- `Archive/web_gui_legacy_*` removed from repository history surface.

## [0.9.1] - 2026-03-29 (backfilled)

### Added
- Adaptive query routing for simple factual/live-event/deep-research/workspace prompt classes.
- Lightweight performance tracing and local summary retrieval helpers.
- Confidence gating in answer composition.

### Changed
- Web research now supports diversity-aware early stopping and TTL page caching.
- Research pathing now uses a light path when confidence/complexity allows.

### Fixed
- Cloud consult logging path cleanup to avoid stale `runs_log_path` failures.

## [0.9.0] - 2026-03-29 (backfilled)

### Added
- Research quality pass covering answer composer improvements, volatility-aware retrieval, and structured combat-sports fact cards.
- New shared modules: `answer_composer.py`, `fact_policy.py`, and `fact_cards.py`.

### Changed
- Source scoring now includes volatility/freshness fit in addition to static source tier.
- Final summaries include improved heading normalization and duplicate cleanup.

### Notes
- `0.9.0` and `0.9.1` entries were backfilled from phase release documents during the v1.0 roadmap pass.
