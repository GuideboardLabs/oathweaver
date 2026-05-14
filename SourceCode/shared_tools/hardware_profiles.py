from __future__ import annotations

import json
import os
from copy import deepcopy
from pathlib import Path
from typing import Any

from scheduler.resource_budget import DEFAULT_PROFILE, HardwareBudgetProfile

ENV_HARDWARE_PROFILE = "OATHWEAVER_HARDWARE_PROFILE"
CONFIG_RELATIVE_PATH = Path("SourceCode") / "configs" / "hardware_profiles.json"


def _coerce_int(value: Any, default: int) -> int:
    try:
        return int(value)
    except Exception:
        return int(default)


def _coerce_float(value: Any, default: float) -> float:
    try:
        return float(value)
    except Exception:
        return float(default)


def _builtin_config() -> dict[str, Any]:
    default = DEFAULT_PROFILE.as_dict()
    return {
        "default_profile": DEFAULT_PROFILE.name,
        "profiles": {
            DEFAULT_PROFILE.name: {
                "name": DEFAULT_PROFILE.name,
                "display_name": "Default: 8GB VRAM / 16GB RAM",
                "description": "Built-in conservative default local profile.",
                "hardware": {
                    "system_ram_gb": default["ram_gb"],
                    "gpu_backend": "generic",
                    "gpu_vram_gb": default["vram_gb"],
                    "unified_memory": False,
                },
                "scheduler": {
                    "max_context_tokens": default["max_context_tokens"],
                    "warning_context_tokens": default["max_context_tokens"],
                    "max_stage_context_tokens": default["max_stage_context_tokens"],
                    "max_parallel_models": default["max_parallel_models"],
                    "max_active_model_calls": default["max_parallel_models"],
                    "on_deck_depth": default["on_deck_depth"],
                    "warm_depth": default["warm_depth"],
                    "allow_neural_prefetch": default["allow_neural_prefetch"],
                },
                "inference": {
                    "preferred_backends": ["ollama", "llama.cpp"],
                    "default_keep_alive": "10m",
                    "heavy_keep_alive": "0",
                    "release_heavy_after_call": True,
                    "max_loaded_models": default["max_parallel_models"],
                },
                "model_policy": {
                    "normal_max_b": 9,
                    "heavy_max_b": 14,
                    "premium_min_b": 24,
                    "allow_premium": False,
                    "premium_requires_manual": True,
                    "allow_14b_with_warning": True,
                    "reject_heavier_fallbacks": False,
                },
                "lane_caps": {},
                "validation": {
                    "startup_mode": "warn",
                    "strict_mode_available": True,
                    "warn_on_missing_models": True,
                    "warn_on_unreachable_backends": True,
                    "warn_on_context_over_cap": True,
                    "warn_on_parallelism_over_cap": True,
                    "warn_on_premium_auto_escalation": True,
                },
            }
        },
    }


def load_hardware_profiles(repo_root: Path) -> dict[str, Any]:
    """Load structured hardware profiles, falling back to the legacy default."""
    config_path = Path(repo_root) / CONFIG_RELATIVE_PATH
    if not config_path.exists():
        return _builtin_config()
    try:
        payload = json.loads(config_path.read_text(encoding="utf-8"))
    except Exception:
        return _builtin_config()
    if not isinstance(payload, dict):
        return _builtin_config()
    profiles = payload.get("profiles")
    if not isinstance(profiles, dict) or not profiles:
        return _builtin_config()
    return payload


def resolve_active_hardware_profile(repo_root: Path, name: str | None = None) -> dict[str, Any]:
    """Resolve the active hardware profile by explicit name, env var, then config default."""
    payload = load_hardware_profiles(repo_root)
    profiles = payload.get("profiles") if isinstance(payload.get("profiles"), dict) else {}
    default_name = str(payload.get("default_profile") or DEFAULT_PROFILE.name).strip() or DEFAULT_PROFILE.name
    requested = str(name or os.getenv(ENV_HARDWARE_PROFILE, "") or default_name).strip()
    if not requested:
        requested = default_name
    key = requested.lower()

    selected: dict[str, Any] | None = None
    for profile_name, profile in profiles.items():
        if str(profile_name).strip().lower() == key and isinstance(profile, dict):
            selected = dict(profile)
            break

    warnings: list[str] = []
    if selected is None:
        fallback = profiles.get(default_name)
        selected = dict(fallback) if isinstance(fallback, dict) else _builtin_config()["profiles"][DEFAULT_PROFILE.name]
        warnings.append(f"Unknown hardware profile {requested!r}; using {selected.get('name', DEFAULT_PROFILE.name)!r}.")

    selected.setdefault("name", requested if not warnings else selected.get("name", DEFAULT_PROFILE.name))
    if warnings:
        selected["_resolution_warnings"] = warnings
    return deepcopy(selected)


def hardware_profile_to_scheduler(profile: dict[str, Any]) -> HardwareBudgetProfile:
    scheduler = profile.get("scheduler") if isinstance(profile.get("scheduler"), dict) else {}
    hardware = profile.get("hardware") if isinstance(profile.get("hardware"), dict) else {}
    return HardwareBudgetProfile(
        name=str(profile.get("name") or DEFAULT_PROFILE.name),
        vram_gb=_coerce_float(hardware.get("gpu_vram_gb"), DEFAULT_PROFILE.vram_gb),
        ram_gb=_coerce_float(hardware.get("system_ram_gb"), DEFAULT_PROFILE.ram_gb),
        max_context_tokens=_coerce_int(scheduler.get("max_context_tokens"), DEFAULT_PROFILE.max_context_tokens),
        max_parallel_models=_coerce_int(scheduler.get("max_parallel_models"), DEFAULT_PROFILE.max_parallel_models),
        on_deck_depth=_coerce_int(scheduler.get("on_deck_depth"), DEFAULT_PROFILE.on_deck_depth),
        warm_depth=_coerce_int(scheduler.get("warm_depth"), DEFAULT_PROFILE.warm_depth),
        max_stage_context_tokens=_coerce_int(
            scheduler.get("max_stage_context_tokens"),
            DEFAULT_PROFILE.max_stage_context_tokens,
        ),
        allow_neural_prefetch=bool(scheduler.get("allow_neural_prefetch", DEFAULT_PROFILE.allow_neural_prefetch)),
    )


def hardware_profile_to_router_policy(profile: dict[str, Any]) -> dict[str, Any]:
    scheduler = profile.get("scheduler") if isinstance(profile.get("scheduler"), dict) else {}
    hardware = profile.get("hardware") if isinstance(profile.get("hardware"), dict) else {}
    model_policy = profile.get("model_policy") if isinstance(profile.get("model_policy"), dict) else {}
    lane_caps = profile.get("lane_caps") if isinstance(profile.get("lane_caps"), dict) else {}
    return {
        "name": str(profile.get("name") or DEFAULT_PROFILE.name),
        "max_context": _coerce_int(scheduler.get("max_context_tokens"), DEFAULT_PROFILE.max_context_tokens),
        "warning_context": _coerce_int(
            scheduler.get("warning_context_tokens"),
            _coerce_int(scheduler.get("max_context_tokens"), DEFAULT_PROFILE.max_context_tokens),
        ),
        "max_concurrency": _coerce_int(
            scheduler.get("max_active_model_calls"),
            _coerce_int(scheduler.get("max_parallel_models"), DEFAULT_PROFILE.max_parallel_models),
        ),
        "allow_premium": bool(model_policy.get("allow_premium", False)),
        "normal_max_b": _coerce_float(model_policy.get("normal_max_b"), 9.0),
        "heavy_max_b": _coerce_float(model_policy.get("heavy_max_b"), 14.0),
        "premium_min_b": _coerce_float(model_policy.get("premium_min_b"), 24.0),
        "premium_requires_manual": bool(model_policy.get("premium_requires_manual", True)),
        "allow_14b_with_warning": bool(model_policy.get("allow_14b_with_warning", True)),
        "reject_heavier_fallbacks": bool(model_policy.get("reject_heavier_fallbacks", False)),
        "gpu_backend": str(hardware.get("gpu_backend") or "generic"),
        "gpu_vram_gb": _coerce_float(hardware.get("gpu_vram_gb"), DEFAULT_PROFILE.vram_gb),
        "lane_caps": deepcopy(lane_caps),
    }


def hardware_profile_summary(profile: dict[str, Any]) -> dict[str, Any]:
    scheduler_profile = hardware_profile_to_scheduler(profile)
    scheduler = profile.get("scheduler") if isinstance(profile.get("scheduler"), dict) else {}
    summary = scheduler_profile.as_dict()
    summary.update(
        {
            "display_name": str(profile.get("display_name") or profile.get("name") or scheduler_profile.name),
            "description": str(profile.get("description") or ""),
            "warning_context_tokens": _coerce_int(
                scheduler.get("warning_context_tokens"),
                scheduler_profile.max_context_tokens,
            ),
            "max_active_model_calls": _coerce_int(
                scheduler.get("max_active_model_calls"),
                scheduler_profile.max_parallel_models,
            ),
            "hardware": deepcopy(profile.get("hardware") if isinstance(profile.get("hardware"), dict) else {}),
            "scheduler": deepcopy(profile.get("scheduler") if isinstance(profile.get("scheduler"), dict) else {}),
            "inference": deepcopy(profile.get("inference") if isinstance(profile.get("inference"), dict) else {}),
            "model_policy": deepcopy(profile.get("model_policy") if isinstance(profile.get("model_policy"), dict) else {}),
            "lane_caps": deepcopy(profile.get("lane_caps") if isinstance(profile.get("lane_caps"), dict) else {}),
            "validation": deepcopy(profile.get("validation") if isinstance(profile.get("validation"), dict) else {}),
        }
    )
    if isinstance(profile.get("_resolution_warnings"), list):
        summary["resolution_warnings"] = list(profile.get("_resolution_warnings") or [])
    return summary


def active_router_policy_from_env(repo_root: Path) -> dict[str, Any] | None:
    """Return a router policy only when the operator explicitly selected a profile."""
    selected = str(os.getenv(ENV_HARDWARE_PROFILE, "")).strip()
    if not selected:
        return None
    return hardware_profile_to_router_policy(resolve_active_hardware_profile(repo_root, selected))
