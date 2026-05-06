from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class HardwareBudgetProfile:
    name: str
    vram_gb: float
    ram_gb: float
    max_context_tokens: int
    max_parallel_models: int
    on_deck_depth: int
    warm_depth: int
    max_stage_context_tokens: int
    allow_neural_prefetch: bool

    def as_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "vram_gb": self.vram_gb,
            "ram_gb": self.ram_gb,
            "max_context_tokens": self.max_context_tokens,
            "max_parallel_models": self.max_parallel_models,
            "on_deck_depth": self.on_deck_depth,
            "warm_depth": self.warm_depth,
            "max_stage_context_tokens": self.max_stage_context_tokens,
            "allow_neural_prefetch": self.allow_neural_prefetch,
        }


DEFAULT_PROFILE = HardwareBudgetProfile(
    name="8gb_vram_16gb_ram",
    vram_gb=8.0,
    ram_gb=16.0,
    max_context_tokens=4096,
    max_parallel_models=1,
    on_deck_depth=1,
    warm_depth=1,
    max_stage_context_tokens=1800,
    allow_neural_prefetch=True,
)


class ResourceBudgetManager:
    def __init__(self, profile: HardwareBudgetProfile | None = None) -> None:
        self.profile = profile or DEFAULT_PROFILE

    def stage_context_budget(self, requested_tokens: int | None = None) -> int:
        env = str(os.getenv("OATHWEAVERX_MAX_STAGE_CONTEXT_TOKENS", "")).strip()
        configured = self.profile.max_stage_context_tokens
        if env:
            try:
                configured = int(env)
            except Exception:
                configured = self.profile.max_stage_context_tokens
        if requested_tokens is None:
            return max(256, int(configured))
        return max(256, min(int(requested_tokens), int(configured), int(self.profile.max_context_tokens)))

    def can_prefetch_neural(
        self,
        *,
        memory_state: dict[str, Any] | None,
        adapter_required: bool,
    ) -> bool:
        if not self.profile.allow_neural_prefetch:
            return False
        if not adapter_required:
            return False
        row = dict(memory_state or {})
        free_vram = row.get("free_vram_gb")
        if free_vram is None:
            free_vram = self.profile.vram_gb * 0.15
        try:
            free_vram_val = float(free_vram)
        except Exception:
            free_vram_val = 0.0
        return free_vram_val >= 1.0

    def prefetch_depths(self) -> tuple[int, int]:
        return max(0, int(self.profile.on_deck_depth)), max(0, int(self.profile.warm_depth))
