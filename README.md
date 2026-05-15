![Oathweaver Banner](docs/images/banner.png)

# Oathweaver

![Backend](https://img.shields.io/badge/Python-3.10+-blue)
![Frontend](https://img.shields.io/badge/VueJS-3.5.13-purple)
![Runtime](https://img.shields.io/badge/runtime-Local--Only-darkgreen)
![LLM](https://img.shields.io/badge/LLM-Ollama-black)
![Status](https://img.shields.io/badge/status-Release%20Candidate%20(0.9.x)-yellow)
![License](https://img.shields.io/badge/license-Service--Only%20Source--Available-orange)

**Self-hosted AI workspace. No API keys. No cloud. No subscriptions. No frontier model calls. Ever.**

Oathweaver is a local-only AI workspace for research, writing, and software generation. Every request flows through a typed pipeline engine, executed through ordered stages backed by a library of typed specialist skill packs and a scoped context-augmented memory layer. Everything runs on your own hardware, on models you control, with data that never leaves your machine.

There is no external API integration and there never will be. The architecture is deliberately closed to frontier providers.

## Why Oathweaver

| | Oathweaver | Frontier AI |
|---|---|---|
| **Runs on** | Your own hardware | Provider's servers |
| **AI models** | Any Ollama-compatible or llama.cpp model | Locked to provider |
| **Your data** | Stays on your machine — always | Sent to vendor |
| **API keys** | None required, none accepted | Required |
| **Cost** | Free after hardware setup | Ongoing subscription |
| **Offline** | Fully functional without internet | Requires connectivity |
| **Customizable** | Full source — fork and modify | Black box |

---

## Start Here (10 minutes)

### Fresh clone

```bash
git clone https://github.com/GuideboardLabs/Oathweaver.git
cd Oathweaver
```

### Linux (Ubuntu 24.04 / 22.04 LTS)

```bash
chmod +x install_oathweaver_linux.sh
./install_oathweaver_linux.sh
```

Then start the app:

```bash
sudo systemctl start oathweaver
# or
./start_oathweaver.sh
```

### Windows

```powershell
git clone https://github.com/GuideboardLabs/Oathweaver.git
cd Oathweaver
powershell -ExecutionPolicy Bypass -File .\install_oathweaver.ps1
powershell -ExecutionPolicy Bypass -File .\start_oathweaver_web.ps1
```

Open: `http://127.0.0.1:5050`

For recipient-friendly install steps, see [INSTALL_GUIDE.md](INSTALL_GUIDE.md).

---

## Phase 0 Stripdown

Oathweaver is in a CAG-native rebuild phase. Legacy surfaces have now been removed:

- **Personal/life memory capture** has been removed.
- **Image generation lanes** have been removed from the repository.  
  Longform `video_script` remains a writing format (text output only), not a media-generation lane.
- **Serious mode** defaults on (`OATHWEAVERX_SERIOUS_MODE=1`) — research, build, and writing pipelines run with evidence discipline and no playful framing.

See [SourceCode/legacy/README.md](SourceCode/legacy/README.md) for migration notes.

---

## Architecture

Oathweaver is built around five cooperating layers.

### 1. Pipeline Engine

Every non-trivial request is mapped onto a typed `PipelineSpec` with a fixed input contract, ordered stages, and a final stage. Three canonical pipelines are defined in [SourceCode/core/pipeline_engine/specs.py](SourceCode/core/pipeline_engine/specs.py):

| Pipeline | Stages |
|---|---|
| `research_pipeline` | intake → domain_framing → source_discovery → evidence_analysis → nuance_pass → synthesis → cag_promotion_gate |
| `build_pipeline` | requirements → architecture → implementation_plan → patch_artifact_generation → verification |
| `code_fix_pipeline` | planner → code_localizer → patch_writer → reviewer → test_fixer → finalizer |

Each stage emits an output that is checked against an **OutputContract** ([SourceCode/core/output_contracts/](SourceCode/core/output_contracts/)) before downstream stages run. Contract failures surface as findings — they do not silently propagate as fabrication or truncation.

### 2. Specialist Skill Packs

Stages are parameterized by a library of typed specialist skill packs in [SourceCode/specialists/](SourceCode/specialists/). Each pack ships as a `SpecialistSkillPack` (role prompt, output schema, CAG query profile, retrieval template, few-shot library, tool permissions, verifier rubric).

| Role | Typical stages |
|---|---|
| `planner` | intake, requirements, architecture, implementation_plan, patch_writer |
| `researcher` | domain_framing, source_discovery, code_localizer |
| `auditor` | evidence_analysis |
| `skeptic` | nuance_pass, reviewer |
| `synthesizer` | synthesis, finalizer |
| `verifier` | verification, test_fixer |
| `memory_critic` | cag_promotion_gate |

Role selection is derived from `(stage, domain, make_type, research_focus)` — for runtime-systems work in computer science, for example, the planner role becomes a `runtime_architect`, the auditor becomes a `benchmark_designer`, and the skeptic becomes a `systems_skeptic`. The pipeline engine resolves the role at planning time, then bakes the matching skill pack's role prompt, schema, and verifier rubric into the stage's context pack. Specialist modules are configuration, not autonomous agents — there is no separate dispatch loop; the model executing the stage is whatever the routing config selects for that lane.

### 3. CAG Memory Layer

Context Accumulation Generation memory ([SourceCode/cag/](SourceCode/cag/)) is the long-lived knowledge substrate. Memory rows are tagged with a `ScopeRow` across five levels:

```
domain → topic → thread → project → run
```

The CAG layer provides:

- **`CAGMemoryStore`** — typed, scoped memory with lifecycle states.
- **`ScopedSelector`** — retrieval scored by scope match, recency, and reputation.
- **`PromotionGate`** — gates memory promotions across scope levels (run → project → thread → topic → domain).
- **`ContradictionDetector`** — flags conflicting claims before promotion.
- **`DecisionLedger`** — append-only record of decisions with provenance.

### 4. Auditor + Trace Ledger

Every stage write goes through a trace ledger. The auditor layer ([SourceCode/auditor/](SourceCode/auditor/)) provides:

- **`TraceAnalyzer`** — finding-typed analysis over emitted traces.
- **`AuditorEngine`** (implication engine) — derives downstream implications from new evidence.
- **`BenchmarkImport`** — pulls external benchmark results into the project kernel.
- **`RegressionReporter`** — diffs current runs against a baseline corpus.

Combined with [SourceCode/core/replay/](SourceCode/core/replay/) and [SourceCode/core/state_store/](SourceCode/core/state_store/), any run is replayable from any node, and semantic drift across replays is reportable.

### 5. Scheduler + Resource Budget

The scheduler ([SourceCode/scheduler/](SourceCode/scheduler/)) decides what runs and when:

- **`SpecialistRegistry`** — manifest-based registry of available specialists per role.
- **`ResourceBudgetManager`** — context, concurrency, and active-model budget, initialized from the active hardware profile (see [Hardware Profile](#hardware-profile)).
- **`OnDeckRuntime`** — keeps a small pool of warm specialists ready for the next stage.
- **`BenchManager`** — coordinates benchmark execution against the budget.

A **Watchtower** layer ([SourceCode/watchtower/](SourceCode/watchtower/)) — knowledge gap detector, project readiness assessor, research card store, and scout — runs at the end of each pipeline turn and on explicit kernel-command invocation. Detected gaps are queued as research cards on disk and surfaced through the Web GUI's watchtower panel for manual review. Card consumption is operator-driven today; no autonomous agent acts on queued cards.

---

## Build Surfaces (Make Pools)

Build-pipeline runs are fronted by purpose-built pools that fill in stage outputs for a specific class of artifact. All pools are local-only, multi-agent, and emit through the same output-contract / trace pipeline.

| Pool | Path | Purpose |
|---|---|---|
| Tool | [agents_tool/tool_pool.py](SourceCode/agents_tool/tool_pool.py) | Single-file Python 3.12+ CLIs / scripts with a self-fix loop |
| Web app | [agents_make/app_pool.py](SourceCode/agents_make/app_pool.py) | Flask 3.x + Vue 3.5 (CDN) + SQLite, built on the fixed Canon v1 scaffold via slot-fills |
| Desktop app | [agents_make/desktop_pool.py](SourceCode/agents_make/desktop_pool.py) | .NET 8 + Avalonia 11 + ReactiveUI MVVM scaffold, Windows-first with Linux portability |
| UI | [agents_ui/ui_pool.py](SourceCode/agents_ui/ui_pool.py) | Flask backend + vanilla-JS frontend with a UX reviewer pass |
| Essay | [agents_make/essay_pool.py](SourceCode/agents_make/essay_pool.py) | Short-to-medium essays / briefs / blogs with topic-aware templates |
| Longform | [agents_make/longform_pool.py](SourceCode/agents_make/longform_pool.py) | Guides, tutorials, video scripts, newsletters, press releases with word-count enforcement |
| Content | [agents_make/content_pool.py](SourceCode/agents_make/content_pool.py) | Blog posts, social posts, emails — feedback-learning informed |
| Specialist | [agents_make/specialist_pool.py](SourceCode/agents_make/specialist_pool.py) | Domain-validated outputs (medical / finance / sports / history / game design) |
| Creative | [agents_make/creative_pool.py](SourceCode/agents_make/creative_pool.py) | Novel / memoir / book / screenplay with continuity-aware scene writers |

The Web app pool uses a **Canon v1** fixed scaffold ([agents_make/canon/web_app_v1/](SourceCode/agents_make/canon/web_app_v1/)) with named slot regions. The pool only fills slots; plumbing is asserted intact by the canon lints. **Extend Mode** copies a prior canon build and updates only the slots required by new features; legacy pre-canon builds are migrated into canon slots on first extend.

Make hardening includes a **runtime smoke** pass for generated Canon v1 apps and a **Public-content guardrail** for blogs, emails, social posts, and other outward-facing writing so private profile hints are not pulled into public drafts unless explicitly requested.

---

## Taxonomy

A typed taxonomy ([SourceCode/taxonomy/](SourceCode/taxonomy/)) drives specialist selection, prompt assembly, and pool routing.

- **Domains** — `computer_science_programming`, `mathematics`, `science`, `history`, `writing_rhetoric`, `business_strategy`, `law_policy`, `engineering`, `creative`, `general_research`.
- **Make types** — ~30 typed artifact targets across five families: programming, writing (serious), writing (creative), strategy / planning, research artifacts.
- **Research focus** — implementation-focused, evidence-focused, comparative, exploratory.

The combination `(domain, make_type, research_focus)` selects the pipeline, the specialist alias for each stage, and the CAG query profile.

---

## Research Surface

Research-pipeline runs are executed by [SourceCode/agents_research/](SourceCode/agents_research/) under the `researcher` / `auditor` / `skeptic` / `synthesizer` specialist roles. Behavior:

- **Tree-planned breadth/depth research** — the planner decomposes the root question into a leaf tree before any leaf is executed.
- **Evidence discipline** — every finding is labeled `[E]` (evidence-backed), `[I]` (inferred), or `[S]` (speculative). The auditor stage rejects unsupported claims.
- **Citation linker** — synthesized text is post-processed sentence-by-sentence against retrieved chunks; cosine-misaligned citations are dropped rather than passed through as fabrication.
- **Skeptic sidecar** — the skeptic pass writes its rationale to a separate `*.critique.md` file linked from the artifact block.
- **Web research cache** — content-addressed SQLite cache with volatility-tiered TTL (24h general, 2h recency-sensitive, 10m live events).
- **Stack-decision guard** — outside a `technical` topic, requests that are purely stack-choice comparisons (SQLite vs Postgres, Flask vs FastAPI) are short-circuited with a re-routing nudge.

The optional **Web research stack** (SearXNG + Crawl4AI, Docker) provides live web foraging.

---

## Conversation Surface (Chat Layer)

User-facing messaging is mediated by the **chat layer** (`hf.co/unsloth/Qwen3-8B-GGUF:UD-Q5_K_XL`, configured under `chat_layer` in `model_routing.json`). The chat layer is *not* the orchestrator — it sits above the kernel and dispatches into pipelines.

**Two-stage routing gate.** Every incoming request is first scored by a semantic-router layer (embedding lookup against known web vs. no-web exemplars, ~20ms) and only falls through to the `qwen3:4b` intent confirmer for genuinely ambiguous messages. A second `qwen3:4b` context gate validates the routing decision against full conversation history before a research pipeline fires.

**Fixed-stack capability injection.** For coding make_types, stack/framework/database choice is treated as system-fixed by default:

- `cli_tool` / `developer_tool` → Python 3.12+ single-file/CLI stack
- `web_app` → Flask 3.x + Vue 3.5 (CDN) + SQLite (`sqlite3`)
- `desktop_app` → .NET 8 LTS + Avalonia 11 + ReactiveUI

Re-evaluation of stack is routed through a Technical topic / Technical-domain research pipeline.

**Live self-awareness.** Conversation-lane turns pass through a `SelfQueryGate` ([SourceCode/orchestrator/services/self_query_gate.py](SourceCode/orchestrator/services/self_query_gate.py)) that detects self-introspection questions ("what model are you running?", "what GPU am I on?", "what's your fallback chain?"). On a hit, a `SelfStateService` ([SourceCode/orchestrator/services/self_state.py](SourceCode/orchestrator/services/self_state.py)) composes a snapshot from `InferenceRouter` diagnostics, the active hardware profile, and the capability registry, and injects it into the system prompt as authoritative context. The chat layer answers configuration questions from live state — not from training-data assumptions or static manifesto text. Non-self-query turns pay zero overhead.

---

## Turn Orchestration (LangGraph)

Every chat turn runs through a LangGraph `StateGraph` defined in [SourceCode/orchestrator/pipelines/turn_graph.py](SourceCode/orchestrator/pipelines/turn_graph.py):

```
ingest → prompt_digest → intent_confirm → lane_route → context_gate
       → lane_execute → compose → persist
```

State is checkpointed at every node boundary into `Runtime/state/turn_checkpoints.sqlite` via `SqliteSaver`. Past turns can be replayed end-to-end or resumed from a specific node via [turn_replay.py](SourceCode/orchestrator/pipelines/turn_replay.py); the regression harness ([regression.py](SourceCode/orchestrator/pipelines/regression.py)) re-runs a curated set of past turns against current code and flags semantic drift via embedding cosine.

---

## Interfaces

Oathweaver ships four interface frontends on top of the same kernel ([SourceCode/interfaces/](SourceCode/interfaces/)):

| Interface | Path | Notes |
|---|---|---|
| Web GUI | [SourceCode/web_gui/](SourceCode/web_gui/) | Flask app — primary UI, served on port 5050 |
| OpenAI-compatible API | [interfaces/api/server.py](SourceCode/interfaces/api/server.py) | Local `/v1/*` endpoints over the kernel |
| CLI | [interfaces/cli/](SourceCode/interfaces/cli/) | Single-shot kernel commands |
| TUI | [interfaces/tui/](SourceCode/interfaces/tui/) | Textual-based terminal UI (plain-mode REPL fallback) |

Optional bot adapters in [SourceCode/bots/](SourceCode/bots/) wrap the kernel for Discord, Slack, and Telegram.

---

## Model Distribution

| Task | Model | Context |
|---|---|---|
| Chat layer (user-facing weavers) | hf.co/unsloth/Qwen3-8B-GGUF:UD-Q5_K_XL | 8,192 |
| Orchestration / reasoning | hf.co/unsloth/Qwen3-8B-GGUF:UD-Q5_K_XL (`think=true`) | 12,288 |
| Research & synthesis | hf.co/unsloth/Qwen3-8B-GGUF:UD-Q5_K_XL | 12,288 |
| Creative writing | hf.co/unsloth/Qwen3-8B-GGUF:UD-Q5_K_XL | 12,288 |
| Premium / longform (when available) | hf.co/bartowski/DeepSeek-R1-Distill-Qwen-32B-GGUF:Q4_K_M (reasoning premium), deepseek-r1:8b (fallback), qwen3-coder:30b-a3b-q4_K_M (coding premium lock) | 16,384 |
| Code (web apps) | qwen3-coder:30b-a3b-q4_K_M | 12,288 |
| Desktop app scaffold | qwen3-coder:30b-a3b-q4_K_M | 16,384 |
| Plan mode (plan-only lane) | hf.co/bartowski/DeepSeek-R1-Distill-Qwen-32B-GGUF:Q4_K_M (`think=true`) | 16,384 |
| Intent gate | qwen3:4b | 4,096 |
| Routing context gate | qwen3:4b | 4,096 |
| Embeddings / RAG / semantic routing | qwen3-embedding:4b | — |
| Make-type classifier | Keyword model (artifact-backed) | CPU |

All models run locally via Ollama or llama.cpp. Assignments are configurable in [SourceCode/configs/model_routing.json](SourceCode/configs/model_routing.json).

---

## Inference Backends

Oathweaver supports two local inference backends:

- **Ollama** — default backend; handles most models via the Ollama API.
- **llama.cpp** (OpenAI-compatible endpoint) — for TurboQuant and custom quantized models; configured per-model under `llama_cpp_servers` in `model_routing.json`.

The inference router auto-falls back to Ollama if a configured llama.cpp server is unreachable. Server backoff is 180s after failure.

The router also exposes a diagnostic surface used by the self-awareness layer and the OpenAI-compatible API:

- `list_backends()` — configured backends with reachability and loaded-model counts
- `fallback_chain(model)` — ordered fallback candidates for a primary model
- `memory_state()` — currently loaded models, VRAM use, KV-cache pressure (live `ollama ps`)
- `capabilities(model)` — size, weight class, context window, premium flag, supported tasks
- `estimate_fit(model, num_ctx, concurrency, profile=...)` — conservative policy estimate against the active hardware profile
- `health_report()` / `explain_route()` / `validate_config()` — full health + routing-decision explanation + profile-aware config validation

These are read-only inspections — they do not change routing decisions on the request path.

---

## Hardware Profile

Local capacity is declared in [SourceCode/configs/hardware_profiles.json](SourceCode/configs/hardware_profiles.json) and resolved at orchestrator startup. The active profile drives the scheduler's `ResourceBudgetManager`, the inference router's `estimate_fit()` and `validate_config()` policies, and the diagnostic surfaces.

Resolution order: explicit kernel-command argument → `OATHWEAVER_HARDWARE_PROFILE` env var → config `default_profile` → built-in conservative default (`8gb_vram_16gb_ram`).

A profile declares hardware capacity (VRAM, RAM, GPU backend), scheduler caps (context tokens, parallel models, on-deck depth), inference policy (preferred backends, keep-alive, max loaded models), model policy (weight-class thresholds, premium gating), per-lane caps, and a validation mode. See the [example shape](SourceCode/configs/hardware_profiles.json) for the full schema.

Enforcement is **advisory-first**: profile mismatches surface as warnings through `validate_config()` rather than hard-blocking startup or model calls. Operators can flip startup_mode to `strict` in the profile to escalate.

---

## Architecture Diagram

```
                  ┌─────────────────────────────────────────┐
                  │       Interfaces                         │
                  │   Web GUI · OpenAI API · CLI · TUI       │
                  └──────────────┬──────────────────────────┘
                                 │
                  ┌──────────────▼──────────────────────────┐
                  │   Chat Layer (Qwen3-8B UD-Q5_K_XL)       │
                  │   semantic-router → intent (qwen3:4b)    │
                  │   → context gate (qwen3:4b)              │
                  │   → self-query gate → self-state inject  │
                  └──────────────┬──────────────────────────┘
                                 │
                  ┌──────────────▼──────────────────────────┐
                  │   Turn Graph (LangGraph)                 │
                  │   8-node StateGraph · SqliteSaver        │
                  │   checkpointing · replay                 │
                  └──────────────┬──────────────────────────┘
                                 │
                  ┌──────────────▼──────────────────────────┐
                  │   Pipeline Engine                        │
                  │   research_pipeline · build_pipeline ·   │
                  │   code_fix_pipeline                      │
                  │   stage outputs gated by OutputContracts │
                  └──────┬──────────────────────────┬───────┘
                         │                          │
            ┌────────────▼──────────┐    ┌──────────▼─────────┐
            │   Specialists         │    │   Build Pools      │
            │   planner · researcher│    │   tool · web_app   │
            │   auditor · skeptic   │    │   desktop · ui     │
            │   synthesizer ·       │    │   essay · longform │
            │   verifier ·          │    │   content ·        │
            │   memory_critic       │    │   specialist ·     │
            └────────────┬──────────┘    │   creative         │
                         │               └──────────┬─────────┘
                         │                          │
                  ┌──────▼──────────────────────────▼───────┐
                  │   CAG Memory Layer                       │
                  │   scoped store (domain→run) · selector · │
                  │   promotion gate · contradiction detect ·│
                  │   decision ledger                        │
                  └──────────────┬──────────────────────────┘
                                 │
                  ┌──────────────▼──────────────────────────┐
                  │   Auditor + Trace Ledger                 │
                  │   trace analysis · implication engine ·  │
                  │   benchmark import · regression reports  │
                  └──────────────┬──────────────────────────┘
                                 │
                  ┌──────────────▼──────────────────────────┐
                  │   Scheduler + Watchtower                 │
                  │   specialist registry · resource budget ·│
                  │   on-deck runtime · gap detector · scout │
                  └──────────────┬──────────────────────────┘
                                 │
                  ┌──────────────▼──────────────────────────┐
                  │   Local Inference                        │
                  │   Ollama · llama.cpp                     │
                  │   health-check + adaptive fallback       │
                  └──────────────┬──────────────────────────┘
                                 │
                  ┌──────────────▼──────────────────────────┐
                  │   Optional External Services            │
                  │   SearXNG · Crawl4AI · MCP (stdio)       │
                  └─────────────────────────────────────────┘
```

---

## Platform Support

| Platform | Status | Notes |
|---|---|---|
| Ubuntu 24.04 LTS | Tested (primary) | Preferred for GPU inference |
| Ubuntu 22.04 LTS | Tested | Installer supports this target |
| Windows 11 | Tested | Installer + web launcher supported |
| Other Linux distros | Experimental | May work, not in tested matrix |
| macOS | Untested | No official support commitment |

---

## Requirements

- **Python 3.10+**
- **Ollama** running locally (required)
- **Docker** (optional — for web research stack: SearXNG + Crawl4AI)
- **Core Python deps** (via `requirements.lock`): LangGraph + SqliteSaver for turn orchestration, semantic-router for fast routing, a lightweight keyword classifier for Make-type routing, MCP SDK for tool surface
- **Optional extras**
  - `requirements-optional-docs.txt` — PDF / DOCX / OCR helpers
  - `requirements-optional-bots.txt` — Discord bot support
- **GPU drivers** (optional but strongly recommended)
  - AMD: ROCm 6.x — RX 5000 series and newer
  - NVIDIA: CUDA toolkit — GTX 10xx and newer, any RTX series

---

## Optional Web Research Stack

Powers the Research pipeline's live web research. Requires Docker.

Linux:

```bash
./start_web_foraging_stack.sh
```

Windows:

```powershell
powershell -ExecutionPolicy Bypass -File .\start_web_foraging_stack.ps1
```

Default service ports:

| Service | Port |
|---|---:|
| SearXNG | 8080 |
| Crawl4AI | 11235 |

---

## MCP (Model Context Protocol)

Oathweaver exposes its research and memory surface as an MCP server — external tools (editors, assistants, other local agents) can call `forage`, `recall`, and `make_artifact` over stdio without touching the web GUI.

```bash
python -m orchestrator.mcp
```

Stdio is the default transport. HTTP is gated behind an explicit config flag and is localhost-only by default; enable with care if you're exposing over Tailscale.

Oathweaver also consumes external MCP servers (filesystem, fetch) via [SourceCode/shared_tools/mcp_client.py](SourceCode/shared_tools/mcp_client.py) — configured in `SourceCode/configs/mcp_servers.json`.

---

## Policies

- **Action policy** ([SourceCode/policies/action_policy.json](SourceCode/policies/action_policy.json)) — content filtering off; explicit approval required for sending messages, calendar booking, purchases, data deletion, and external submissions. Default mode is `draft_then_confirm`.
- **Personal safety policy** ([SourceCode/policies/personal_safety_policy.md](SourceCode/policies/personal_safety_policy.md)) — Oathweaver's personal-assistant role is operational (reminders, accountability, next actions). It is explicitly **not** a therapy or medical-diagnosis role. Personal memory is stored under `Runtime/memory/personal` and gated by Phase 0 quarantine.

---

## Security Notes

- Oathweaver is local-only. No data is ever transmitted to an external AI provider.
- The Web GUI and Ollama both bind to `127.0.0.1` by default. Exposing beyond loopback is an explicit opt-in via `OATHWEAVER_WEB_HOST` / `OLLAMA_HOST` (or the corresponding installer/launcher flags).
- When binding the Web GUI beyond loopback, set `OATHWEAVER_WEB_PASSWORD`. The first-boot owner-setup flow is otherwise reachable to anyone who can hit the port.
- Session cookies are `HTTPOnly` and `SameSite=Strict`. Setting `OATHWEAVER_HTTPS=1` also enables `Secure` cookies so credentials never travel cleartext.
- The action policy gate (`OATHWEAVER_APPROVAL_GATE`) defaults to enabled. Action policy is `draft_then_confirm` for sending messages, calendar booking, purchases, data deletion, and external submissions.
- The OpenAI-compatible local API server defaults to localhost. If exposing beyond loopback, gate it via the local Bearer-token mechanism documented in [interfaces/api/server.py](SourceCode/interfaces/api/server.py).
- Secret-bearing config files (e.g. `Runtime/config/bot_config.json`) are written with mode `0600`.
- The MCP HTTP transport is gated behind an explicit config flag and is localhost-only by default.

## Local Hardware Profiles

Shared defaults live in `SourceCode/configs/hardware_profiles.json`. Host-specific tuning belongs in
`SourceCode/configs/hardware_profiles.local.json`, which is ignored by git and merged over the shared config
at startup. Select a profile with `OATHWEAVER_HARDWARE_PROFILE`.

```json
{
  "default_profile": "local_8gb_vram_48gb_ram_cuda",
  "profiles": {
    "local_8gb_vram_48gb_ram_cuda": {
      "name": "local_8gb_vram_48gb_ram_cuda",
      "display_name": "Local: 48GB RAM / 8GB CUDA",
      "hardware": {
        "system_ram_gb": 48,
        "gpu_backend": "cuda",
        "gpu_vram_gb": 8,
        "unified_memory": false
      },
      "scheduler": {
        "max_context_tokens": 12288,
        "warning_context_tokens": 8192,
        "max_stage_context_tokens": 2400,
        "max_parallel_models": 1,
        "max_active_model_calls": 1,
        "on_deck_depth": 1,
        "warm_depth": 0,
        "allow_neural_prefetch": false
      }
    }
  }
}
```

---

## Repository Layout

| Path | Purpose |
|---|---|
| `SourceCode/core/` | Pipeline engine, output contracts, capability registry, model runtime, project kernel, state store, trace ledger, replay, context compiler, context pack, kernel commands |
| `SourceCode/cag/` | Context Accumulation Generation memory: scope, lifecycle, memory store, scoped selector, promotion gate, contradiction detector, decision ledger |
| `SourceCode/specialists/` | Specialist skill packs (planner, researcher, auditor, skeptic, synthesizer, verifier, memory_critic) |
| `SourceCode/auditor/` | Trace analysis, implication engine, benchmark import, regression reporter |
| `SourceCode/scheduler/` | Specialist registry, resource budget, on-deck runtime, bench manager |
| `SourceCode/watchtower/` | Knowledge gap detector, project readiness, research card store, scout |
| `SourceCode/taxonomy/` | Domain, make-type, and research-focus taxonomies |
| `SourceCode/orchestrator/` | Top-level orchestrator, intent routing, turn graph, MCP bridge, identity / manifesto |
| `SourceCode/orchestrator/pipelines/` | LangGraph turn state machine, replay, regression harness |
| `SourceCode/orchestrator/services/` | Intent confirmer, semantic gate, chat routing gate, self-query gate, self-state composer, Make-type classifier, agent contracts/registry |
| `SourceCode/agents_research/` | Research pool: tree planner, deep researcher, synthesizer, citation linker, topic policy |
| `SourceCode/agents_make/` | Build pools (essay, longform, content, specialist, creative, web app, desktop) + Canon v1 web scaffold |
| `SourceCode/agents_tool/` | Tool pool (single-file Python with self-fix loop) |
| `SourceCode/agents_ui/` | UI pool (Flask + vanilla JS) and UX reviewer |
| `SourceCode/interfaces/` | Web GUI, OpenAI-compatible API, CLI, TUI frontends |
| `SourceCode/web_gui/` | Flask web GUI (primary interface) |
| `SourceCode/infra/` | Persistence, background workers, infra tooling |
| `SourceCode/shared_tools/` | Inference router (+ diagnostics), hardware profile loader, memory systems, research tools, activity bus, Phase 0 flags |
| `SourceCode/policies/` | Action policy and personal safety policy |
| `SourceCode/legacy/` | Phase 0 quarantine notes |
| `SourceCode/bots/` | Discord, Slack, Telegram bot adapters |
| `SourceCode/benchmark/` | Benchmark runner: fires research-pool questions and reports output quality metrics |
| `SourceCode/benchmarks/` | Hardware profiles and CAG benchmark adapter |
| `SourceCode/configs/model_routing.json` | Model assignments, inference servers, fallback config |
| `SourceCode/configs/hardware_profiles.json` | Hardware profile definitions (capacity, scheduler caps, model policy, lane caps) |
| `scripts/` | Training utilities for the make-type keyword classifier and low-confidence flagging |
| `tests/` | Test suite |
| `docs/` | Architecture notes, changelogs, planning artifacts |
| `tools/` | Utility scripts: health checks, developer tooling |
| `Runtime/` | Local runtime state (generated at runtime; user-owned) |
| `Projects/` | Generated outputs and artifacts |

---

## Configuration

Primary config files:

- `SourceCode/configs/model_routing.json` — model assignments per layer (chat, orchestrator reasoning, research pool, etc.), llama.cpp server entries, premium-model list, context sizes.
- `SourceCode/configs/hardware_profiles.json` — hardware profile definitions; selects the active profile via `default_profile` and feeds the scheduler + inference router with capacity caps and model policy.
- `SourceCode/configs/mcp_servers.json` — external MCP servers consumed by Oathweaver.

Environment flags:

- `OATHWEAVER_HARDWARE_PROFILE` — pick the active hardware profile by name (overrides config `default_profile`). Resolution falls back to the config default and then to the built-in conservative profile.
- `OATHWEAVER_APPROVAL_GATE` — default `1` (enabled). Gates message-send, calendar booking, purchases, data deletion, and external submissions through `draft_then_confirm`. Set to `0` to disable.
- `OATHWEAVER_WEB_HOST` / `OATHWEAVER_WEB_PORT` — bind address and port for the Web GUI. Defaults to `127.0.0.1:5050`. Use an explicit non-loopback value to expose over LAN/Tailscale.
- `OATHWEAVER_WEB_PASSWORD` — required when binding beyond loopback.
- `OATHWEAVER_HTTPS` — when `1`, the web GUI sets `SESSION_COOKIE_SECURE` so cookies do not travel over plain HTTP.
- `OLLAMA_HOST` — defaults to `127.0.0.1:11434`. Change only if you understand the LAN-exposure implications (Ollama has no built-in auth).
- `OATHWEAVERX_SERIOUS_MODE` — default `1`. Set to `0` to allow playful framing in writing pipelines.

Useful startup scripts:

- `start_oathweaver_web.sh` (Linux, host/port flags)
- `start_oathweaver_web.ps1` (Windows)

---

## Development Workflow

Provision a dev environment:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.lock
```

Run the standard check suite:

```bash
make check
```

Run checks individually:

```bash
python3 smoke_test.py
python3 run_integration_tests.py
python3 tools/ui_phase_smoke.py
python3 tools/browser_headless_smoke.py
python3 tools/repo_health_check.py
```

Maintenance utilities:

```bash
python3 tools/refresh_requirements_lock.py   # regenerate requirements.lock
python3 tools/reset_environment.py           # reset local dev environment
python3 scripts/train_make_classifier.py     # retrain the make-type keyword classifier
python3 scripts/flag_low_confidence.py       # flag low-confidence classifier predictions
```

Optional feature installs:

```bash
pip install -r requirements-optional-docs.txt
pip install -r requirements-optional-bots.txt
```

---

## Packaging and Distribution

Create a clean distributable ZIP:

```powershell
powershell -ExecutionPolicy Bypass -File .\create_clean_zip.ps1
```

GitHub-friendly ZIP (include docs/images, exclude installer EXE):

```powershell
powershell -ExecutionPolicy Bypass -File .\create_clean_zip.ps1 -IncludeDocsAndImages -IncludeInstallerExe:$false
```

Build installer EXE:

```powershell
powershell -ExecutionPolicy Bypass -File .\build_installer_exe.ps1
```

---

## Troubleshooting

### Ollama not responding

Linux:
```bash
sudo systemctl restart ollama
sudo journalctl -u ollama -n 50
```

Windows:
```powershell
ollama serve
```

### Oathweaver not starting

Linux:
```bash
sudo journalctl -u oathweaver -n 50
```

Windows: re-run the start script and check terminal output.

### GPU not used by Ollama

AMD (Linux):
```bash
rocm-smi
groups $USER
# If render/video groups missing:
sudo usermod -aG render,video $USER
# Log out and back in
```

If you need to build Ollama with GFX1010 support (RX 5000 series):
```bash
bash tools/build_ollama_gfx1010.sh
```

NVIDIA (Linux):
```bash
nvidia-smi
# If not found, reboot and check again
```

### Port conflict on web startup

Linux:
```bash
sudo systemctl edit oathweaver
# Add: Environment="OATHWEAVER_WEB_PORT=5051"
sudo systemctl restart oathweaver
```

Windows:
```powershell
powershell -ExecutionPolicy Bypass -File .\start_oathweaver_web.ps1 -WebPort 5051
```

---

## Changelog and Release Notes

- [CHANGELOG.md](CHANGELOG.md)
- [docs/release_notes_v0.9.2-rc.md](docs/release_notes_v0.9.2-rc.md)
- [docs/release_notes_phase18_optimization.md](docs/release_notes_phase18_optimization.md)
- [docs/release_notes_phase17_research_quality.md](docs/release_notes_phase17_research_quality.md)
- [docs/changelogs/phase19_accuracy_semantic_ui.md](docs/changelogs/phase19_accuracy_semantic_ui.md)
- [docs/changelogs/phase18c_confidence_and_memory.md](docs/changelogs/phase18c_confidence_and_memory.md)
- [docs/changelogs/phase18b_research_speed.md](docs/changelogs/phase18b_research_speed.md)
- [docs/changelogs/phase18a_query_routing.md](docs/changelogs/phase18a_query_routing.md)

---

## Docs Index

- [INSTALL_GUIDE.md](INSTALL_GUIDE.md) — recipient-focused install guide
- [CONTRIBUTING.md](CONTRIBUTING.md) — contribution workflow and standards
- [SECURITY.md](SECURITY.md) — security reporting policy and scope
- [RELEASE_PROCESS.md](RELEASE_PROCESS.md) — release gates, tagging flow, and artifact process
- [UPGRADE_GUIDE.md](UPGRADE_GUIDE.md) — upgrade and rollback guidance
- [Workspace tools](docs/workspace_tools.md) — utility scripts and tooling notes
- [Phase changelogs](docs/changelogs/) — milestone-level updates
- [Historical docs archive](docs/changelogs/historical/README.md) — archived planning and phase notes

---

## Project Status

Oathweaver is functional, actively used, and tracking toward a stable 1.0. The current series (`0.9.x`) is a **release candidate**: the architecture and primary surfaces (pipelines, CAG, chat layer, build pools, interfaces) are stable enough to depend on, with pending work scoped and tracked rather than open-ended.

What is stable:
- The five-layer architecture and the three canonical pipelines
- Local-only operation; no path to a frontier provider
- The four interfaces (Web GUI, OpenAI-compatible API, CLI, TUI) and the shared kernel they sit on
- Inference router with diagnostics, fallback chain, and streaming watchdog
- Hardware profile as explicit runtime policy
- Self-awareness layer for live configuration queries
- Approval gate, action policy, and security defaults (loopback binds, `SameSite=Strict`, `0600` secret files)

What is still moving toward 1.0:
- Decomposition of the largest source files (`orchestrator/main.py`, `web_research.py`, `app_pool.py`, `deep_researcher.py`)
- Memory-layer consolidation (the CAG memory facade unifies most read paths; the last source merge is in progress)
- Integration test coverage for the orchestrator main paths and Web GUI routes

APIs and config formats are unlikely to break inside `0.9.x`, but the `1.0` cut may rename some surfaces. Pin to a specific `0.9.x` tag if that matters to you.

- CI runs on Python 3.10 and 3.12 on every push/PR
- Tested on Ubuntu 24.04 LTS (primary), Ubuntu 22.04 LTS, and Windows 11
- GPU acceleration via AMD ROCm or NVIDIA CUDA; CPU-only also works

---

## Contributing

Contributions are welcome. See [CONTRIBUTING.md](CONTRIBUTING.md).

---

## License

Oathweaver is released under the [Guideboard Service-Only License 1.0](LICENSE).

- Commercial services around the software are allowed (consulting, integration, support).
- Selling the software product itself is not allowed.
- This is source-available, not an OSI open source license.

Dependency license notes are in [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md).
