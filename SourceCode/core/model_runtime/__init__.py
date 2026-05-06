from __future__ import annotations

import os
from pathlib import Path

from .base import GenerateRequest, ModelRuntime
from .llamacpp import LlamaCppModelRuntime
from .ollama import OllamaModelRuntime


def build_model_runtime(repo_root: Path, *, backend: str = "") -> ModelRuntime:
    key = str(backend or os.getenv("OATHWEAVERX_MODEL_RUNTIME", "ollama")).strip().lower()
    if key in {"llamacpp", "llama.cpp", "llama_cpp"}:
        return LlamaCppModelRuntime(Path(repo_root))
    return OllamaModelRuntime(Path(repo_root))


__all__ = [
    "GenerateRequest",
    "ModelRuntime",
    "OllamaModelRuntime",
    "LlamaCppModelRuntime",
    "build_model_runtime",
]
