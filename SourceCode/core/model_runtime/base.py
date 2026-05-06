from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class GenerateRequest:
    model: str
    system_prompt: str
    user_prompt: str
    prior_messages: list[dict[str, str]] | None = None
    user_images: list[str] | None = None
    temperature: float = 0.3
    num_ctx: int = 8192
    think: bool | None = None
    num_predict: int | None = -1
    timeout: int = 300


class ModelRuntime(ABC):
    """Backend-agnostic model runtime contract.

    Phase 11 boundary: core scheduling and pipelines call this abstraction,
    not backend-shaped client internals.
    """

    @abstractmethod
    def generate(self, request: GenerateRequest) -> str:
        raise NotImplementedError

    @abstractmethod
    def embed(self, texts: list[str], *, model: str) -> list[list[float]]:
        raise NotImplementedError

    @abstractmethod
    def tokenize(self, text: str, *, model: str = "") -> list[int]:
        raise NotImplementedError

    @abstractmethod
    def get_context_limit(self, *, model: str = "") -> int:
        raise NotImplementedError

    @abstractmethod
    def get_memory_state(self) -> dict[str, Any]:
        """Return current runtime memory pressure and loaded-model state.

        Expected keys (when known):
        - backend
        - loaded_model
        - loaded_models
        - loaded_adapter
        - kv_pressure
        - free_vram_gb
        - free_ram_gb
        - context_limit
        """
        raise NotImplementedError
