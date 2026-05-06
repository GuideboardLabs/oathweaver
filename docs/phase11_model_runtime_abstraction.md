# Phase 11 Model Runtime Abstraction

Phase 11 adds a backend-neutral model runtime boundary so core scheduling/pipeline logic no longer depends on Ollama-shaped internals.

## Added modules

- `SourceCode/core/model_runtime/base.py`
  - `ModelRuntime` abstract contract.
  - `GenerateRequest` request shape.

- `SourceCode/core/model_runtime/ollama.py`
  - `OllamaModelRuntime` implementation using existing router/client stack.
  - Implements `get_memory_state()` from Ollama `/api/ps` so scheduler can read loaded model, adapter, VRAM headroom, and KV pressure.

- `SourceCode/core/model_runtime/llamacpp.py`
  - `LlamaCppModelRuntime` implementation for llama.cpp server deployments.

- `SourceCode/core/model_runtime/__init__.py`
  - `build_model_runtime(...)` factory (`OATHWEAVERX_MODEL_RUNTIME` or explicit backend).

## Scheduler integration

- `SourceCode/core/pipeline_engine/engine.py`
  - `PipelineEngine.execute(...)` now accepts optional `model_runtime`.
  - Before each stage's on-deck plan call, engine queries `model_runtime.get_memory_state()` and injects `payload["model_memory_state"]`.

- `SourceCode/orchestrator/main.py`
  - Instantiates `self.model_runtime = build_model_runtime(repo_root)`.
  - Passes `model_runtime=self.model_runtime` into `pipeline_engine.execute(...)`.

This satisfies the phase requirement that On-Deck scheduling uses runtime memory state.

## Verification target

With this boundary, swapping from Ollama to llama.cpp only changes runtime selection (`build_model_runtime`), not pipeline/scheduler core logic.
