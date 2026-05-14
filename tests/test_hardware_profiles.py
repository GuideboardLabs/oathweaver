from __future__ import annotations

import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock

from tests.common import ROOT  # noqa: F401

from shared_tools.hardware_profiles import (
    CONFIG_RELATIVE_PATH,
    ENV_HARDWARE_PROFILE,
    hardware_profile_to_router_policy,
    hardware_profile_to_scheduler,
    resolve_active_hardware_profile,
)
from shared_tools.inference_router import InferenceRouter


CUSTOM_PROFILE_NAME = "test_cuda_profile"


def _write_custom_profiles(repo_root: Path) -> None:
    config_path = repo_root / CONFIG_RELATIVE_PATH
    config_path.parent.mkdir(parents=True, exist_ok=True)
    config_path.write_text(
        json.dumps(
            {
                "default_profile": "8gb_vram_16gb_ram",
                "profiles": {
                    "8gb_vram_16gb_ram": {
                        "name": "8gb_vram_16gb_ram",
                        "hardware": {
                            "system_ram_gb": 16,
                            "gpu_backend": "generic",
                            "gpu_vram_gb": 8,
                            "unified_memory": False,
                        },
                        "scheduler": {
                            "max_context_tokens": 4096,
                            "warning_context_tokens": 4096,
                            "max_stage_context_tokens": 1800,
                            "max_parallel_models": 1,
                            "max_active_model_calls": 1,
                            "on_deck_depth": 1,
                            "warm_depth": 1,
                            "allow_neural_prefetch": True,
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
                        "validation": {"startup_mode": "warn"},
                    },
                    CUSTOM_PROFILE_NAME: {
                        "name": CUSTOM_PROFILE_NAME,
                        "display_name": "Synthetic CUDA profile",
                        "description": "Synthetic test profile for hardware policy conversion.",
                        "hardware": {
                            "system_ram_gb": 24,
                            "gpu_backend": "cuda",
                            "gpu_vram_gb": 6,
                            "unified_memory": False,
                        },
                        "scheduler": {
                            "max_context_tokens": 6144,
                            "warning_context_tokens": 4096,
                            "max_stage_context_tokens": 1600,
                            "max_parallel_models": 1,
                            "max_active_model_calls": 1,
                            "on_deck_depth": 1,
                            "warm_depth": 0,
                            "allow_neural_prefetch": False,
                        },
                        "inference": {
                            "preferred_backends": ["llama.cpp", "ollama"],
                            "default_keep_alive": "2m",
                            "heavy_keep_alive": "0",
                            "release_heavy_after_call": True,
                            "max_loaded_models": 1,
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
                        "lane_caps": {
                            "chat_layer": {
                                "max_context_tokens": 4096,
                                "max_parallel_agents": 1,
                            }
                        },
                        "validation": {"startup_mode": "warn"},
                    },
                },
            },
            indent=2,
        ),
        encoding="utf-8",
    )


class HardwareProfileTests(unittest.TestCase):
    def setUp(self) -> None:
        self._previous_profile = os.environ.pop(ENV_HARDWARE_PROFILE, None)
        self.tmp = tempfile.TemporaryDirectory(prefix="hardware_profiles_")
        self.repo_root = Path(self.tmp.name)
        _write_custom_profiles(self.repo_root)

    def tearDown(self) -> None:
        os.environ.pop(ENV_HARDWARE_PROFILE, None)
        if self._previous_profile is not None:
            os.environ[ENV_HARDWARE_PROFILE] = self._previous_profile
        self.tmp.cleanup()

    def test_active_profile_resolver_returns_default_when_env_is_unset(self) -> None:
        profile = resolve_active_hardware_profile(self.repo_root)

        self.assertEqual(profile["name"], "8gb_vram_16gb_ram")

    def test_active_profile_resolver_returns_named_profile_from_env(self) -> None:
        os.environ[ENV_HARDWARE_PROFILE] = CUSTOM_PROFILE_NAME

        profile = resolve_active_hardware_profile(self.repo_root)

        self.assertEqual(profile["name"], CUSTOM_PROFILE_NAME)
        self.assertEqual(profile["hardware"]["system_ram_gb"], 24)
        self.assertEqual(profile["scheduler"]["warm_depth"], 0)

    def test_unknown_profile_falls_back_to_default_with_warning(self) -> None:
        profile = resolve_active_hardware_profile(self.repo_root, "not_a_real_profile")

        self.assertEqual(profile["name"], "8gb_vram_16gb_ram")
        self.assertTrue(profile.get("_resolution_warnings"))

    def test_named_profile_converts_to_scheduler_profile(self) -> None:
        profile = resolve_active_hardware_profile(self.repo_root, CUSTOM_PROFILE_NAME)

        scheduler = hardware_profile_to_scheduler(profile)

        self.assertEqual(scheduler.ram_gb, 24.0)
        self.assertEqual(scheduler.vram_gb, 6.0)
        self.assertEqual(scheduler.max_context_tokens, 6144)
        self.assertEqual(scheduler.max_parallel_models, 1)
        self.assertEqual(scheduler.warm_depth, 0)

    def test_named_profile_converts_to_router_policy(self) -> None:
        profile = resolve_active_hardware_profile(self.repo_root, CUSTOM_PROFILE_NAME)

        policy = hardware_profile_to_router_policy(profile)

        self.assertEqual(policy["max_context"], 6144)
        self.assertEqual(policy["warning_context"], 4096)
        self.assertEqual(policy["max_concurrency"], 1)
        self.assertFalse(policy["allow_premium"])

    def test_router_fit_uses_named_policy_when_explicit(self) -> None:
        router = InferenceRouter(self.repo_root)
        policy = hardware_profile_to_router_policy(
            resolve_active_hardware_profile(self.repo_root, CUSTOM_PROFILE_NAME)
        )

        normal = router.estimate_fit("qwen3:8b", 4096, profile=policy)
        premium = router.estimate_fit("qwen3:30b-a3b-q4_K_M", 4096, profile=policy)

        self.assertTrue(normal["fits"])
        self.assertEqual(normal["profile"], CUSTOM_PROFILE_NAME)
        self.assertFalse(premium["fits"])
        self.assertEqual(premium["profile"], CUSTOM_PROFILE_NAME)

    def test_router_fit_uses_env_profile_without_explicit_profile(self) -> None:
        os.environ[ENV_HARDWARE_PROFILE] = CUSTOM_PROFILE_NAME
        router = InferenceRouter(self.repo_root)

        fit = router.estimate_fit("qwen3:8b", 6144, concurrency=1)

        self.assertTrue(fit["fits"])
        self.assertEqual(fit["profile"], CUSTOM_PROFILE_NAME)

    def test_validate_config_warns_when_route_exceeds_profile_lane_caps(self) -> None:
        router = InferenceRouter(self.repo_root)
        router._routing = {
            "chat_layer": {
                "model": "qwen3:8b",
                "num_ctx": 6144,
                "parallel_agents": 2,
            },
            "premium_models": [],
        }
        router.list_backends = MagicMock(return_value=[])
        policy = hardware_profile_to_router_policy(
            resolve_active_hardware_profile(self.repo_root, CUSTOM_PROFILE_NAME)
        )

        report = router.validate_config(check_remote=False, profile=policy)

        self.assertTrue(report["ok"])
        self.assertEqual(report["profile"], CUSTOM_PROFILE_NAME)
        self.assertTrue(any("lane cap" in item for item in report["warnings"]))


if __name__ == "__main__":
    unittest.main()
