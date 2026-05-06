from __future__ import annotations

from pathlib import Path
from typing import Any

from shared_tools.llamacpp_client import LlamaCppClient

from .base import GenerateRequest, ModelRuntime


class LlamaCppModelRuntime(ModelRuntime):
    """ModelRuntime implementation for llama.cpp OpenAI-compatible servers."""

    def __init__(
        self,
        repo_root: Path,
        *,
        client: LlamaCppClient | None = None,
        default_context_limit: int = 8192,
    ) -> None:
        self.repo_root = Path(repo_root)
        self.client = client or LlamaCppClient()
        self.default_context_limit = max(512, int(default_context_limit))

    def generate(self, request: GenerateRequest) -> str:
        return self.client.chat(
            request.model,
            request.system_prompt,
            request.user_prompt,
            prior_messages=request.prior_messages,
            user_images=request.user_images,
            temperature=float(request.temperature),
            num_ctx=int(request.num_ctx),
            think=request.think,
            num_predict=request.num_predict,
            timeout=int(request.timeout),
        )

    def embed(self, texts: list[str], *, model: str) -> list[list[float]]:
        # llama.cpp embedding endpoint support is deployment-specific in this repo.
        raise NotImplementedError("LlamaCppModelRuntime.embed is not available in this configuration")

    def tokenize(self, text: str, *, model: str = "") -> list[int]:
        _ = model
        tokens = [w for w in str(text or "").split() if w.strip()]
        return list(range(len(tokens)))

    def get_context_limit(self, *, model: str = "") -> int:
        _ = model
        return int(self.default_context_limit)

    def get_memory_state(self) -> dict[str, Any]:
        loaded_models = self.client.list_local_models()
        loaded_model = loaded_models[0] if loaded_models else ""
        return {
            "backend": "llama.cpp",
            "loaded_model": loaded_model,
            "loaded_models": loaded_models,
            "loaded_adapter": "",
            "kv_pressure": 0.0,
            "free_vram_gb": 0.0,
            "free_ram_gb": 0.0,
            "context_limit": self.get_context_limit(model=loaded_model),
            "raw_model_count": len(loaded_models),
        }
