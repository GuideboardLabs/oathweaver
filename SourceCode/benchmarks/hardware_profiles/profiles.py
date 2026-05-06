from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from scheduler.resource_budget import HardwareBudgetProfile


@dataclass(frozen=True)
class BenchmarkHardwareProfile:
    name: str
    max_context_tokens: int
    max_parallel_models: int
    on_deck_depth: int
    warm_depth: int
    max_stage_context_tokens: int
    vram_gb: float
    ram_gb: float
    allow_neural_prefetch: bool = True

    def as_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "max_context_tokens": int(self.max_context_tokens),
            "max_parallel_models": int(self.max_parallel_models),
            "on_deck_depth": int(self.on_deck_depth),
            "warm_depth": int(self.warm_depth),
            "max_stage_context_tokens": int(self.max_stage_context_tokens),
            "vram_gb": float(self.vram_gb),
            "ram_gb": float(self.ram_gb),
            "allow_neural_prefetch": bool(self.allow_neural_prefetch),
        }

    def to_scheduler_profile(self) -> HardwareBudgetProfile:
        return HardwareBudgetProfile(
            name=self.name,
            vram_gb=float(self.vram_gb),
            ram_gb=float(self.ram_gb),
            max_context_tokens=int(self.max_context_tokens),
            max_parallel_models=int(self.max_parallel_models),
            on_deck_depth=int(self.on_deck_depth),
            warm_depth=int(self.warm_depth),
            max_stage_context_tokens=int(self.max_stage_context_tokens),
            allow_neural_prefetch=bool(self.allow_neural_prefetch),
        )


PROFILE_8GB_VRAM_16GB_RAM = BenchmarkHardwareProfile(
    name="8gb_vram_16gb_ram",
    max_context_tokens=4096,
    max_parallel_models=1,
    on_deck_depth=1,
    warm_depth=1,
    max_stage_context_tokens=1800,
    vram_gb=8.0,
    ram_gb=16.0,
    allow_neural_prefetch=True,
)

PROFILES: dict[str, BenchmarkHardwareProfile] = {
    PROFILE_8GB_VRAM_16GB_RAM.name: PROFILE_8GB_VRAM_16GB_RAM,
}


def profile_by_name(name: str) -> BenchmarkHardwareProfile:
    key = str(name or "").strip().lower() or PROFILE_8GB_VRAM_16GB_RAM.name
    return PROFILES.get(key, PROFILE_8GB_VRAM_16GB_RAM)
