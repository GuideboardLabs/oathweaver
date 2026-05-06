# Phase 0 Implementation (Strip-down and Rename Pass)

This repo now runs a strict Phase-0 serious runtime with legacy surfaces removed.

## Default-on behaviors

- Serious mode enabled: `OATHWEAVERX_SERIOUS_MODE=1`
- Legacy personal/life memory removed.
- Legacy image/video generation removed from this repo.

## Removed legacy surfaces

- Personal memory capture and web routes are removed.
- Image/video generation list endpoints and UI residue are removed.
- Briefings routes and panel are removed; Watchtower now uses research-card naming only.

## Terminology bridge (Phase 0 aliases)

- `Foraging` -> `Research`:
  - Added `/api/research/state` alias.
  - Added `research_*` alias keys in status payloads.
- `Lane` -> `Pipeline`:
  - Added `pipeline` aliases in routing/worker/registry payloads.
- `Topic Type` -> `Domain`:
  - Added `domain` aliases where topic/profile metadata is surfaced.
- `Briefings` -> `Watchtower Research Cards`:
  - Canonical APIs:
    - `/api/panel/watchtower-research-cards`
    - `/api/watchtower/research-cards/<id>`
    - `/api/watchtower/research-cards/<id>/read|unread`
