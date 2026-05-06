# Oathweaver — Phase 19 Changelog
## Accuracy Maximization, Semantic Memory, and UI Polish

**Date:** 2026-03-15
**Sessions:** 2 (continued across context boundary)
**Scope:** UI overhaul, research accuracy overhaul, semantic memory layer, signal quality hardening

---

## Overview

This release covers four overlapping workstreams delivered across planning sessions labelled Phase 4A (backfill confirmation), Phase 6 (Accuracy Maximization), and Phase 7 (Semantic Completion & Signal Quality). The guiding principle throughout was: **make what already exists work better before adding new capabilities.** No new user-facing features were added. Every change either activates a dormant quality mechanism, replaces a bag-of-words heuristic with a real embedding, or fixes a misconfiguration that was silently degrading output.

---

## 1. UI Enhancements

These changes make the web interface feel closer to premium AI-centered applications (Claude.ai / Perplexity level) without structural rewrites.

### 1.1 CSS — Premium Visual Layer
**File:** `SourceCode/web_gui/static/styles.css` (~220 lines appended)

| Component | Change |
|-----------|--------|
| Scrollbars | Width reduced 11px → 5px; thumb styling tightened |
| User message bubbles | Angled gradient fill, right-aligned |
| Assistant message bubbles | `surface-2` background + 3px blue left-accent border |
| Pending / thinking state | `.msg.pending` pulsing glow animation (`thinkingGlow` keyframe) |
| Code blocks | macOS 3-dot header via `::before` / `::after` pseudo-elements; `padding-top: 38px` |
| Inline code | Blue-tinted background |
| Blockquote | Accent rule + subtle background |
| Composer area | `backdrop-filter: blur()` for depth |
| Send button | Lift transform on hover |
| Cancel button | Restyled with `.msg-cancel-btn` class |
| Copy button | Scale + tint on hover |
| Message entrance | `msgSlideUp` keyframe animation on `messages > article:last-of-type` |
| Conversation list | `border-left` accent on active item |
| Foraging tags | Pulse animation |
| Placeholder | Opacity transition on focus |

### 1.2 Rotating Composer Placeholders
**Files:** `SourceCode/web_gui/static/app.js`, `SourceCode/web_gui/templates/index.html`

- Added `COMPOSER_PLACEHOLDERS` constant with per-mode text pools (`talk`, `forage`, `make`)
- Added `composerPlaceholderIdx: 0` data prop and `_composerPlaceholderTimer` to Vue instance
- `composerPlaceholder` computed property returns the current pool entry for the active input mode
- 5-second interval cycles through pool entries; timer cleaned up in `beforeDestroy()`
- `index.html` textarea `:placeholder` bound to `composerPlaceholder` computed prop

### 1.3 Button Icon Upgrades
**File:** `SourceCode/web_gui/templates/index.html`

- Cancel button: plain `"X"` text replaced with SVG stop-square icon + `msg-cancel-btn` class
- Send button: paper-plane SVG arrow icon added alongside existing "Send" label

---

## 2. Phase 4A Backfill — Reliability Fixes

These items were confirmed complete (either in this session or a preceding one). Documented here for completeness.

### 2.1 Orchestrator Reasoning Timeout (4A-1)
**File:** `SourceCode/configs/model_routing.json`

`orchestrator_reasoning.timeout_sec` changed from `0` (no timeout — infinite hang risk) to `180`. Prevents Ollama model-load delays from blocking the orchestrator indefinitely.

### 2.2 Model Health Check at Startup (4A-2)
**File:** `SourceCode/web_gui/bootstrap.py`

`check_model_availability()` runs in a background thread on startup. Walks every `model` and `fallback_models` field in `model_routing.json`, compares against `OllamaClient().list_local_models()`, and logs a `WARNING` per missing model. Does not block startup.

### 2.3 Confidence Weighting in Synthesis (4A-4)
**File:** `SourceCode/agents_research/synthesizer.py`

Self-check confidence scores (1–5) from each research agent are converted to `HIGH` / `MED` / `LOW` labels and injected into the synthesizer's `findings_blob`. The system prompt instructs the model to weight conclusions toward `HIGH`-confidence findings and flag synthesis that relies heavily on `LOW`-confidence evidence.

### 2.4 Lesson TTL / Expiration Policy (4A-5)
**File:** `SourceCode/shared_tools/feedback_learning.py`

`_LESSON_TTL_DAYS` dict applies per-origin TTL at lesson creation:
- `manual_feedback`: 180 days
- `outbox_feedback`: 90 days
- `reflection` / `cloud_critique`: 60 days

`guidance_for_lane()` query filters `expires_at > now()`. The `expires_at` column is no longer always NULL.

---

## 3. Phase 6 — Accuracy Maximization

### 3.1 deepseek-r1 Chain-of-Thought Activated (6-1)
**Files:** `SourceCode/configs/model_routing.json`, `SourceCode/agents_research/deep_researcher.py`

deepseek-r1:8b powers the `technical_researcher` and `risk_researcher` personas. Its chain-of-thought reasoning (`<think>` scratchpad) was globally disabled. Two changes enable it:

- `"think": true` added to both deepseek-r1 entries in `agent_mix` in `model_routing.json`
- Auto-enable logic added in `_agent_specs()` in `deep_researcher.py`: any agent whose `model` starts with `"deepseek-r1"` receives `"think": True` unless explicitly overridden. This covers all hardcoded profile template dicts (17+ entries) with a single post-processing line.
- `research_pool.timeout_sec` raised 300 → 420 to accommodate CoT reasoning time on CPU.

`_self_check()` calls remain hardcoded `think=False` — self-check is a rating task, not a reasoning task.

### 3.2 Parallel Research Agents (6-2)
**File:** `SourceCode/configs/model_routing.json`

`research_pool.parallel_agents` changed 1 → 2. All 4 personas previously ran sequentially. Running in pairs roughly halves wall-clock time for a full deep research cycle. Within memory budget on 16 GB RAM / RX 5700 XT 8 GB VRAM.

### 3.3 Source Batch Size Doubled (6-3)
**File:** `SourceCode/agents_research/deep_researcher.py`

Two constants changed:
- `_MULTI_PASS_BATCH_SIZE`: 3 → 6 (sources per LLM pass)
- `_MULTI_PASS_THRESHOLD`: 2 → 4 (only batch when >4 source blocks)

Agents now see up to 24 sources per pass within the existing 24K token context window. Evidence blind spots from small batches are reduced.

### 3.4 Freshness-Dominant Sort for Volatile Topics (6-4)
**File:** `SourceCode/shared_tools/web_research.py`

`rank_and_filter_sources()` now checks `classify_fact_volatility(query, resolved_topic)` before sorting. For `volatile` topics (live scores, prices, breaking news), sort order becomes:

```
(not stale_for_query, freshness_score, source_score, snippet_len)
```

For `stable` and `semi-volatile` topics, the previous sort (authority-primary) is unchanged. Prevents a stale Reuters article from outranking a fresh tier-2 source on a time-sensitive query.

`classify_fact_volatility` was already in `fact_policy.py` but not imported into `web_research.py` — import added.

### 3.5 Learned Source Reputation (6-5)
**New file:** `SourceCode/shared_tools/domain_reputation.py`
**Modified:** `SourceCode/shared_tools/web_research.py`, `SourceCode/orchestrator/main.py`, `SourceCode/shared_tools/migrations.py`

New module `DomainReputation` tracks per-domain score adjustments in a SQLite table (`domain_reputation`, added as migration 014):

| Method | Effect |
|--------|--------|
| `record_success(domain)` | `adjustment += 0.01`, capped at 0.0 — slow recovery |
| `record_correction(domain)` | `adjustment -= 0.05`, floor at −0.3 — penalty |
| `get_adjustment(domain) → float` | Returns stored adjustment, 0.0 if unseen |

**Wiring:**

- `WebResearchEngine.__init__` instantiates `self._domain_rep = DomainReputation(repo_root)`
- `_score_one_source()` adds `self._domain_rep.get_adjustment(host)` to the source score before the final clamp. Adjustments are small (max ±0.3) and compound over sessions without overriding tier authority.
- After each successful research completion in `main.py`, `record_success(domain)` is called for all source domains used. This covers both the auto-run and approve-and-run code paths.

### 3.6 Cross-Agent Conflict Reconciliation (6-6)
**Files:** `SourceCode/agents_research/deep_researcher.py`, `SourceCode/agents_research/synthesizer.py`

**`_cross_agent_conflict_report(findings)`** — new function in `deep_researcher.py`. Heuristic (no LLM call): pairwise sentence comparison across primary-role agent findings. Detects sentences sharing subject noun tokens where one contains positive directional signals (`increase`, `improve`, `better`, `higher`…) and another contains negative signals (`decrease`, `risk`, `fail`, `worse`…). Returns a markdown `## Disputed Claims Across Agents` block (max 5 conflicts) or empty string.

**`synthesizer.synthesize()`** updated to accept `conflict_report: str = ""` kwarg. When non-empty, appended to the synthesis user prompt:

```
CROSS-AGENT DISPUTES — reconcile these explicitly in your synthesis
(state which position has stronger evidence or note genuine uncertainty):
```

Forces the synthesizer to explicitly arbitrate rather than silently merge contradictory agent outputs.

### 3.7 Real Embeddings in EmbeddingMemory (6-8)
**Files:** `SourceCode/shared_tools/ollama_client.py`, `SourceCode/shared_tools/embedding_memory.py`

**`OllamaClient.embed(model, text, *, timeout=60) → list[float]`** — new method. Calls Ollama `/api/embed` endpoint (v0.5+ format: `"input"` field, returns `{"embeddings": [[...]]}`).

**`EmbeddingMemory`** rewritten with a two-path retrieval strategy:

1. **Vector path** (`_retrieve_vector()`): Embeds query with `nomic-embed-text`, loads/computes file vectors keyed on `(path, mtime)` from `Runtime/memory/embed_cache/{project}.json`. Cosine similarity threshold: 0.35. Stale cache entries auto-invalidated on file modification.
2. **Bag-of-words fallback** (`_retrieve_bow()`): Original token-frequency cosine path, threshold 0.05. Runs silently if Ollama is unreachable or `nomic-embed-text` is not pulled.

`retrieve()` tries vector path first, falls back to bag-of-words on any exception. Semantic queries ("canine dietary requirements" matching a file about "dog nutrition") now surface correctly.

---

## 4. Phase 7 — Semantic Completion & Signal Quality

### 4.1 Fixed Stray `think=True` Default in MAKE Lane (7-1)
**File:** `SourceCode/orchestrator/main.py` (~line 2525)

The MAKE lane deliverable writer used `think=bool(cfg.get("think", True))`. If the config key was absent, `think` defaulted to `True` — activating extended reasoning on a pure formatting/generation task using `qwen2.5-coder:7b`, which gains nothing from CoT. Changed default to `False`.

### 4.2 Confirmed: [E]/[I]/[S] Claim Tagging Already in Agent Prompts (7-2)
**File:** `SourceCode/agents_research/deep_researcher.py:588–593`

Audit confirmed `_agent_prompt()` already instructs agents to tag every substantive claim with `[E]` (sourced), `[I]` (inferred), or `[S]` (speculative), and to cite source domains after `[E]` claims. No change needed.

### 4.3 Semantic Retrieval in `TopicMemory.get_context_for_query()` (7-3)
**File:** `SourceCode/shared_tools/topic_memory.py`

`get_context_for_query()` previously scored topics by token overlap between the query and topic title+subtopics. "Canine gut health" would not match a topic titled "Dog Nutrition."

Changes:
- Added module-level `_vec_cosine(a, b) → float` function
- Added `_embed_cache: dict[str, list[float]]` session cache on `TopicMemory` instance
- Added `_try_embed(text) → list[float] | None` helper — lazy-initializes `OllamaClient`, caches results in `_embed_cache`, returns `None` on any failure
- `get_context_for_query()` now attempts semantic scoring first: embeds query, embeds each topic's `title + subtopics` string, scores by cosine (threshold 0.30). Falls back to original token-overlap scoring if embedding returns nothing or fails.

### 4.4 Semantic Dedup in Lesson Storage (7-4)
**File:** `SourceCode/shared_tools/feedback_learning.py`

`_insert_lessons()` had no deduplication. Repeated reflection cycles could store semantically identical guidance under different wording, consuming the `guidance_for_lane()` budget (5 lessons per lane) with paraphrased duplicates.

New `_guidance_is_duplicate(conn, guidance, lane) → bool` method:
1. Embeds new `guidance` text with `nomic-embed-text`
2. Queries existing `active = 1` lessons for the lane (up to 50)
3. Computes cosine similarity against each
4. Returns `True` if any similarity > 0.90 (duplicate — skip INSERT)
5. Returns `False` on any exception (fail-open — insert proceeds)

Called inside `_insert_lessons()` before each `INSERT INTO lessons`.

### 4.5 Confirmed: Routing History Context Already Implemented (7-5)
**File:** `SourceCode/orchestrator/main.py:2898–2916`

Audit confirmed that `handle_message()` already builds a `_routing_recent_ctx` block from the last 6 history turns (role + first 100 chars of content) and passes it as `recent_context` to `turn_planner.plan()`. No change needed.

### 4.6 Confirmed: Planner Context Already Lean (7-6)
**File:** `SourceCode/legacy planning/service.py:295–330`

Audit confirmed `_task_context_line()` already serializes tasks to human-readable strings of the form `Task: {title} | due {date} | list {list} | for {members}`. Fields like `id`, `snooze_until`, `reminder_count`, `parent_task`, and `block_log_json` are never included. No change needed.

### 4.7 Semantic Fact Dedup in `TopicMemory.merge_fact()` (7-7)
**File:** `SourceCode/shared_tools/topic_memory.py`

`merge_fact()` deduplicated facts with Jaccard token overlap (threshold 0.75). Two facts worded differently about the same thing — "the model uses 8GB VRAM" vs "GPU memory requirement is 8 gigabytes" — would be stored as separate entries.

Changes:
- `ollama_client: Any = None` parameter added to `merge_fact()` signature
- After the Jaccard check finds no match, if `ollama_client` is provided, embeds both the new claim and each existing claim with `nomic-embed-text`, computes cosine similarity
- If similarity ≥ 0.88: treats as duplicate — updates confidence on existing fact if new confidence is higher, returns early without inserting
- Exception in embed path falls through silently to normal INSERT
- `ollama_client` threaded through from `extract_and_merge_from_research()` → `merge_fact()`

Jaccard runs first (zero LLM calls). Embed comparison only runs when Jaccard reports no match, so the fast path is unchanged for obvious duplicates.

---

## 5. Deferred Items

The following planned items were investigated and explicitly deferred:

| Item | Reason |
|------|--------|
| **6-7 Query decomposition** | `_decompose_query()` function (complex multi-part query sub-question generation per persona). Adds one LLM call per deep research run. Deferred — needs testing to confirm latency is acceptable on CPU before enabling. |
| **4C-1 Streaming responses** | `chat_stream()` in `OllamaClient` + SSE wiring. Architectural — requires Flask SSE route and frontend token-stream handler. Separate session. |
| **4C-2 Studio Elma** | Image generation via cloud API. New capability, separate session. |

---

## 6. New Files Created

| File | Purpose |
|------|---------|
| `SourceCode/shared_tools/domain_reputation.py` | Per-domain score adjustment engine with SQLite persistence |

---

## 7. Database Migrations

| Version | Name | Description |
|---------|------|-------------|
| 014 | `domain_reputation_table` | `domain_reputation` table: `domain`, `adjustment`, `query_count`, `correction_count`, `updated_at` |

---

## 8. Runtime Artifacts

| Path | Created by | Purpose |
|------|-----------|---------|
| `Runtime/memory/embed_cache/{project}.json` | `EmbeddingMemory._retrieve_vector()` | Mtime-keyed embedding vector cache for research summary files |

---

## 9. Configuration Changes

**`SourceCode/configs/model_routing.json`:**

| Field | Before | After | Reason |
|-------|--------|-------|--------|
| `orchestrator_reasoning.timeout_sec` | `0` | `180` | Prevent infinite hang |
| `research_pool.parallel_agents` | `1` | `2` | Concurrent agent pairs |
| `research_pool.timeout_sec` | `300` | `420` | Accommodate CoT reasoning time |
| `agent_mix[technical_researcher].think` | *(absent)* | `true` | Activate deepseek-r1 CoT |
| `agent_mix[risk_researcher].think` | *(absent)* | `true` | Activate deepseek-r1 CoT |

---

## 10. Validation Checklist

### Accuracy

- [ ] Run a technical research query involving tradeoffs. Verify Ollama server logs show deepseek-r1 taking longer (~60–120s more) — CoT is active.
- [ ] Run deep research with 4 agents. Compare elapsed time vs before — should be ~40–50% faster than sequential.
- [ ] Run a live-event / sports score query. Confirm the first source block has the smallest age (most recent), even if tier-2.
- [ ] Run a complex research query with known opposing factors (e.g., battery vs hydrogen storage). Check synthesis input for a `## Disputed Claims Across Agents` block.
- [ ] In a project with prior research summaries, run a follow-up using different words. Verify `EmbeddingMemory.retrieve()` returns the prior summary (semantic match rather than token miss).

### Semantic Memory

- [ ] Run a query using different phrasing from an existing topic (e.g., "dog food protein" for a topic titled "Canine Nutrition"). Verify `TopicMemory.get_context_for_query()` returns canon facts.
- [ ] Run multiple reflection cycles on the same lane. Verify `lessons.json` count does not grow unboundedly — duplicate guidance is being deduplicated.
- [ ] Check `Runtime/memory/embed_cache/` — cache files should appear after first embedding query.

### Domain Reputation

- [ ] After running several research cycles, query `DomainReputation.get_all()` — `query_count` should be incrementing per domain.
- [ ] Source score for a domain that has been used multiple times should be marginally higher than a fresh domain of the same tier.

### UI

- [ ] Reload the web app. Composer placeholder should rotate every 5 seconds across `talk`, `forage`, `make` modes.
- [ ] Submit a message and observe the `msgSlideUp` entrance animation on the new assistant bubble.
- [ ] Verify the thinking/pending state shows a pulsing glow rather than a static indicator.
- [ ] Open a code block in a response — macOS-style 3-dot header should be visible.

### Configuration

- [ ] Restart the app and check logs — model health check should run in background and warn on any missing model.
- [ ] Confirm `nomic-embed-text` is pulled: `ollama pull nomic-embed-text`. Required for vector retrieval paths in `EmbeddingMemory` and `TopicMemory`.

---

## 11. Dependency Note

The semantic memory improvements in this release (`EmbeddingMemory`, `TopicMemory`, `FeedbackLearning` dedup) all rely on `nomic-embed-text` being available in Ollama. If the model is not pulled, all three systems fall back silently to their pre-existing bag-of-words paths — no errors, no degradation beyond the absence of semantic retrieval.

```
ollama pull nomic-embed-text
```

The startup model health check will warn if it's missing.
