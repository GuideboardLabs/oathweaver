![Oathweaver Banner](docs/images/banner.png)

# Oathweaver

![Backend](https://img.shields.io/badge/Python-3.10+-blue)
![Frontend](https://img.shields.io/badge/VueJS-3.5.13-purple)
![Runtime](https://img.shields.io/badge/runtime-Local--Only-darkgreen)
![LLM](https://img.shields.io/badge/LLM-Ollama-black)
![Status](https://img.shields.io/badge/status-Experimental-yellow)
![License](https://img.shields.io/badge/license-Service--Only%20Source--Available-orange)

**Self-hosted AI workspace. No API keys. No cloud. No subscriptions. No frontier model calls. Ever.**

Oathweaver is a local-only AI workspace for research, writing, and software generation. Every request flows through a typed pipeline engine, executed by a roster of specialist agents over a scoped context-augmented memory layer. Everything runs on your own hardware, on models you control, with data that never leaves your machine.

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
- **Image / video generation lanes** have been removed from the repository.
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

### 2. Specialist Roster

Stages are executed by a fixed roster of specialist agents in [SourceCode/specialists/](SourceCode/specialists/). Each specialist ships as a `SpecialistSkillPack` (role prompt, output schema, CAG query profile, retrieval template, few-shot library, tool permissions, verifier rubric).

| Specialist | Typical stages |
|---|---|
| `planner` | intake, requirements, architecture, implementation_plan, patch_writer |
| `researcher` | domain_framing, source_discovery, code_localizer |
| `auditor` | evidence_analysis |
| `skeptic` | nuance_pass, reviewer |
| `synthesizer` | synthesis, finalizer |
| `verifier` | verification, test_fixer |
| `memory_critic` | cag_promotion_gate |

Specialist selection is derived from `(stage, domain, make_type, research_focus)` — for runtime-systems work in computer science, for example, the planner becomes a `runtime_architect`, the auditor becomes a `benchmark_designer`, and the skeptic becomes a `systems_skeptic`.

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
- **`ResourceBudgetManager`** — per-hardware-profile budget for context, concurrency, and active models.
- **`OnDeckRuntime`** — keeps a small pool of warm specialists ready for the next stage.
- **`BenchManager`** — coordinates benchmark execution against the budget.

A **Watchtower** layer ([SourceCode/watchtower/](SourceCode/watchtower/)) — knowledge gap detector, project readiness assessor, research card store, and scout — runs alongside the kernel to surface what is missing before the user has to ask.

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

User-facing messaging is mediated by the **chat layer** (`dolphin3:8b`, configured under `chat_layer` in `model_routing.json`). The chat layer is *not* the orchestrator — it sits above the kernel and dispatches into pipelines.

**Two-stage routing gate.** Every incoming request is first scored by a semantic-router layer (embedding lookup against known web vs. no-web exemplars, ~20ms) and only falls through to the `gemma3:4b` intent confirmer for genuinely ambiguous messages. A second `qwen3:4b` context gate validates the routing decision against full conversation history before a research pipeline fires.

**Fixed-stack capability injection.** For coding make_types, stack/framework/database choice is treated as system-fixed by default:

- `cli_tool` / `developer_tool` → Python 3.12+ single-file/CLI stack
- `web_app` → Flask 3.x + Vue 3.5 (CDN) + SQLite (`sqlite3`)
- `desktop_app` → .NET 8 LTS + Avalonia 11 + ReactiveUI

Re-evaluation of stack is routed through a Technical-domain research pipeline.

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
| Chat layer (user-facing weavers) | dolphin3:8b | 8,192 |
| Orchestration / reasoning | deepseek-r1:8b (`think=true`) | 12,288 |
| Research & synthesis | qwen3:8b | 12,288 |
| Creative writing | qwen3:8b | 12,288 |
| Unrestricted-topic content | huihui_ai/qwen3-abliterated:8b-Q4_K_M | 8,192 |
| Premium / longform (when available) | qwen2.5:32b, deepseek-r1:14b, qwen2.5-coder:14b | 16k–24k |
| Code (web apps) | qwen2.5-coder:7b / :14b | 12,288 |
| Desktop app scaffold | qwen2.5-coder:14b | 16,384 |
| Intent gate | gemma3:4b | 4,096 |
| Routing context gate | qwen3:4b | 4,096 |
| Embeddings / RAG / semantic routing | qwen3-embedding:4b | — |
| Make-type classifier | SetFit over sentence-transformers | CPU |

All models run locally via Ollama or llama.cpp. Assignments are configurable in [SourceCode/configs/model_routing.json](SourceCode/configs/model_routing.json).

---

## Inference Backends

Oathweaver supports two local inference backends:

- **Ollama** — default backend; handles most models via the Ollama API.
- **llama.cpp** (OpenAI-compatible endpoint) — for TurboQuant and custom quantized models; configured per-model under `llama_cpp_servers` in `model_routing.json`.

The inference router auto-falls back to Ollama if a configured llama.cpp server is unreachable. Server backoff is 180s after failure.

---

## Architecture Diagram

```
                  ┌─────────────────────────────────────────┐
                  │       Interfaces                         │
                  │   Web GUI · OpenAI API · CLI · TUI       │
                  └──────────────┬──────────────────────────┘
                                 │
                  ┌──────────────▼──────────────────────────┐
                  │   Chat Layer (dolphin3:8b)               │
                  │   semantic-router → intent (gemma3:4b)   │
                  │   → context gate (qwen3:4b)              │
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
- **Core Python deps** (via `requirements.lock`): LangGraph + SqliteSaver for turn orchestration, semantic-router for fast routing, SetFit + sentence-transformers for Make-type classification, MCP SDK for tool surface
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
- Startup scripts can bind to all interfaces (`0.0.0.0`) for LAN/Tailscale access.
- Use loopback (`127.0.0.1`) to restrict to local access only.
- Configure host/port via `OATHWEAVER_WEB_HOST` and `OATHWEAVER_WEB_PORT`.
- Set `OATHWEAVER_WEB_PASSWORD` when exposing beyond localhost.

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
| `SourceCode/orchestrator/services/` | Intent confirmer, semantic gate, chat routing gate, Make-type classifier, agent contracts/registry |
| `SourceCode/agents_research/` | Research pool: tree planner, deep researcher, synthesizer, citation linker, topic policy |
| `SourceCode/agents_make/` | Build pools (essay, longform, content, specialist, creative, web app, desktop) + Canon v1 web scaffold |
| `SourceCode/agents_tool/` | Tool pool (single-file Python with self-fix loop) |
| `SourceCode/agents_ui/` | UI pool (Flask + vanilla JS) and UX reviewer |
| `SourceCode/interfaces/` | Web GUI, OpenAI-compatible API, CLI, TUI frontends |
| `SourceCode/web_gui/` | Flask web GUI (primary interface) |
| `SourceCode/infra/` | Persistence, background workers, infra tooling |
| `SourceCode/shared_tools/` | Inference router, memory systems, research tools, activity bus, Phase 0 flags |
| `SourceCode/policies/` | Action policy and personal safety policy |
| `SourceCode/legacy/` | Phase 0 quarantine notes |
| `SourceCode/bots/` | Discord, Slack, Telegram bot adapters |
| `SourceCode/benchmark/` | Benchmark runner: fires research-pool questions and reports output quality metrics |
| `SourceCode/benchmarks/` | Hardware profiles and CAG benchmark adapter |
| `SourceCode/configs/model_routing.json` | Model assignments, inference servers, fallback config |
| `scripts/` | ML training scripts for the SetFit make-type classifier and low-confidence flagging |
| `tests/` | Test suite |
| `docs/` | Architecture notes, changelogs, planning artifacts |
| `tools/` | Utility scripts: health checks, developer tooling |
| `Runtime/` | Local runtime state (generated at runtime; user-owned) |
| `Projects/` | Generated outputs and artifacts |

---

## Configuration

Primary model and routing config:

- `SourceCode/configs/model_routing.json` — model assignments per layer (chat, orchestrator reasoning, research pool, etc.), llama.cpp server entries, premium-model list, context sizes.

Phase 0 environment flags:

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
python3 scripts/train_make_classifier.py     # retrain the SetFit make-type classifier
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

- [docs/changelogs/phase19_accuracy_semantic_ui.md](docs/changelogs/phase19_accuracy_semantic_ui.md)
- [docs/changelogs/phase18c_confidence_and_memory.md](docs/changelogs/phase18c_confidence_and_memory.md)
- [docs/changelogs/phase18b_research_speed.md](docs/changelogs/phase18b_research_speed.md)
- [docs/changelogs/phase18a_query_routing.md](docs/changelogs/phase18a_query_routing.md)
- [docs/release_notes_phase18_optimization.md](docs/release_notes_phase18_optimization.md)
- [docs/release_notes_phase17_research_quality.md](docs/release_notes_phase17_research_quality.md)

---

## Docs Index

- [INSTALL_GUIDE.md](INSTALL_GUIDE.md) — recipient-focused install guide
- [CONTRIBUTING.md](CONTRIBUTING.md) — contribution workflow and standards
- [Workspace tools](docs/workspace_tools.md) — utility scripts and tooling notes
- [Phase changelogs](docs/changelogs/) — milestone-level updates

---

## Project Status

Oathweaver is functional and actively used. It is in an **experimental** phase — the CAG-native rebuild is in progress, and APIs and config formats may change between releases.

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
