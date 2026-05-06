# Phase 10 Interface Unification Layer

Phase 10 introduces a single kernel command surface and interface adapters so GUI/TUI/CLI/API call shared logic instead of duplicating orchestration paths.

## Core kernel command surface

Added `SourceCode/core/kernel_commands/`:

- `service.py` — `KernelCommandService`
- `factory.py` — `build_kernel_commands(...)`

Supported commands:

- `project_open`
- `pipeline_run`
- `memory_inspect`
- `audit_report`
- `watchtower_scan`
- `benchmark_compare`
- `stage_resume`

## Interfaces

Added `SourceCode/interfaces/{gui,tui,cli,api}/`:

- `interfaces/gui/adapter.py`
  - `GUIKernelAdapter` for GUI routes/controllers.
- `interfaces/tui/`
  - Ported unified TUI command shape with slash-command router and Textual/REPL entrypoint.
- `interfaces/cli/main.py`
  - Scriptable CLI commands for all required phase-10 kernel operations.
- `interfaces/api/server.py`
  - OpenAI-compatible local API (`/v1/chat/completions`, `/v1/models`) plus kernel endpoints.

## Wiring update

- `SourceCode/orchestrator/main.py` remains kernel execution authority.
- `KernelCommandService` wraps orchestrator + CAG + watchtower + auditor artifacts as one shared call surface.
- Interfaces own UI/transport logic only and delegate execution into kernel commands.

## Notes

- API server imports Flask lazily, so non-web test/runtime environments can still import interface modules.
- TUI has a Textual mode when installed, with automatic plain REPL fallback when Textual is unavailable.
