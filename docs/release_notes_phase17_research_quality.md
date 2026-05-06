# Oathweaver Release: Research Quality Pass (Phases 15-17)

This release adds three high-ROI research quality upgrades aimed at moving sports/news/event summaries from "good" to "sharper and more trustworthy":

## Included

### Phase 15 - Better answer composer
- Human-readable source labels (for example: UFC Stats, UFC.com, ESPN, DraftKings Sportsbook)
- Heading normalization for duplicated sections like Open Questions / Unknowns / Key Risks
- Final summary section ordering by schema
- Duplicate paragraph cleanup in final research summaries
- Optional fact-card insertion into research summaries

### Phase 16 - Volatility-aware retrieval
- Query/topic volatility classification (`stable`, `semi_volatile`, `volatile`)
- Freshness scoring attached to retrieved sources
- Stale-source penalty for volatile queries such as odds, timing, live / today / tonight
- Source type metadata (`official`, `news`, `betting`, `reference`)
- Source scoring upgraded to account for freshness fit, not just domain tier

### Phase 17 - Structured fact cards
- Combat-sports fact-card extraction pass for research summaries
- Event-date, broadcast, odds, record, title-history, and injury signal extraction
- Fact-card markdown inserted into composed summaries when topic appears to be UFC / MMA / boxing / fight related

## Main files added
- `SourceCode/shared_tools/answer_composer.py`
- `SourceCode/shared_tools/fact_policy.py`
- `SourceCode/shared_tools/fact_cards.py`

## Main files updated
- `SourceCode/shared_tools/web_research.py`
- `SourceCode/orchestrator/main.py`

## Notes
- These changes are local-first and do not require extra cloud usage.
- The new fact-card logic is intentionally scoped to combat sports first for best ROI.
- Existing research still works if no web sources are available; the new layers degrade gracefully.
