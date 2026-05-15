from __future__ import annotations

import unittest
from unittest.mock import MagicMock

from tests.common import ROOT  # noqa: F401
from shared_tools.inference_router import InferenceRouter


class InferenceRouterCompatTests(unittest.TestCase):
    def test_chat_forwards_num_predict_to_ollama(self) -> None:
        router = InferenceRouter(ROOT)
        router._model_map = {}
        router._ollama = MagicMock()
        router._ollama.chat.return_value = "ok"

        out = router.chat(
            model="qwen3:8b",
            system_prompt="sys",
            user_prompt="user",
            num_predict=321,
            retry_attempts=1,
        )

        self.assertEqual(out, "ok")
        kwargs = router._ollama.chat.call_args.kwargs
        self.assertEqual(kwargs.get("num_predict"), 321)

    def test_chat_forwards_num_predict_to_llama_cpp(self) -> None:
        router = InferenceRouter(ROOT)
        router._model_map = {"qwen3:8b": "llama_srv"}
        router._llama_clients = {"llama_srv": MagicMock()}
        router._fallback_flags = {"llama_srv": False}
        router._llama_clients["llama_srv"].chat.return_value = "ok"
        router._server_declares_model = MagicMock(return_value=True)

        out = router.chat(
            model="qwen3:8b",
            system_prompt="sys",
            user_prompt="user",
            num_predict=777,
            retry_attempts=1,
        )

        self.assertEqual(out, "ok")
        kwargs = router._llama_clients["llama_srv"].chat.call_args.kwargs
        self.assertEqual(kwargs.get("num_predict"), 777)

    def test_wait_for_available_uses_llama_declaration_without_chat(self) -> None:
        router = InferenceRouter(ROOT)
        router._server_declares_model = MagicMock(side_effect=lambda m: m == "deepseek-r1:8b")
        router._ollama = MagicMock()
        router.chat = MagicMock(side_effect=AssertionError("preflight must not call chat"))

        self.assertTrue(
            router.wait_for_available(
                "qwen3:8b",
                fallback_models=["deepseek-r1:8b"],
                max_wait_sec=1,
                poll_interval_sec=1,
            )
        )
        router.chat.assert_not_called()
        router._ollama.wait_for_available.assert_not_called()

    def test_wait_for_available_delegates_to_ollama_without_chat(self) -> None:
        router = InferenceRouter(ROOT)
        router._server_declares_model = MagicMock(return_value=False)
        router._ollama = MagicMock()
        router._ollama.wait_for_available.return_value = True
        router._ollama.last_wait_polls = 2
        router._ollama.last_wait_error = ""
        router.chat = MagicMock(side_effect=AssertionError("preflight must not call chat"))

        self.assertTrue(
            router.wait_for_available(
                "qwen3:8b",
                fallback_models=["deepseek-r1:8b"],
                max_wait_sec=1,
                poll_interval_sec=1,
            )
        )
        router.chat.assert_not_called()
        kwargs = router._ollama.wait_for_available.call_args.kwargs
        self.assertEqual(router._ollama.wait_for_available.call_args.args[0], "qwen3:8b")
        self.assertEqual(kwargs.get("fallback_models"), ["deepseek-r1:8b"])

    def test_list_backends_includes_ollama_and_llama_cpp(self) -> None:
        router = InferenceRouter(ROOT)
        router._routing = {
            "llama_cpp_servers": {
                "fast_lane": {
                    "base_url": "http://127.0.0.1:8180",
                    "models": ["qwen3:8b"],
                    "fallback_to_ollama": True,
                }
            }
        }
        router._ollama = MagicMock()
        router._ollama.list_local_models.return_value = ["phi4-mini:3.8b"]
        router._llama_clients = {"fast_lane": MagicMock()}
        router._llama_clients["fast_lane"].base_url = "http://127.0.0.1:8180"
        router._llama_clients["fast_lane"].list_local_models_strict.return_value = ["qwen3:8b"]
        router._model_map = {"qwen3:8b": "fast_lane"}
        router._fallback_flags = {"fast_lane": True}

        backends = router.list_backends()

        self.assertEqual(backends[0]["name"], "ollama")
        self.assertTrue(backends[0]["reachable"])
        self.assertEqual(backends[1]["name"], "fast_lane")
        self.assertTrue(backends[1]["reachable"])
        self.assertEqual(backends[1]["configured_models"], ["qwen3:8b"])

    def test_fallback_chain_deduplicates_and_preserves_order(self) -> None:
        router = InferenceRouter(ROOT)
        router._routing = {
            "chat_layer": {
                "model": "qwen3:8b",
                "fallback_models": ["deepseek-r1:8b", "qwen3:8b", "qwen2.5-coder:7b"],
            },
            "synthesis": {
                "model": "qwen3:8b",
                "synthesis_fallback_models": ["deepseek-r1:8b", "phi4:14b"],
            },
        }

        self.assertEqual(
            router.fallback_chain("qwen3:8b"),
            ["qwen3:8b", "deepseek-r1:8b", "qwen2.5-coder:7b", "phi4:14b"],
        )

    def test_is_loaded_uses_ollama_ps_shape(self) -> None:
        router = InferenceRouter(ROOT)
        router._read_ollama_ps_json = MagicMock(
            return_value={
                "models": [
                    {
                        "name": "qwen3:8b",
                        "size_vram": 3 * 1024 * 1024 * 1024,
                        "gpu_total": 8 * 1024 * 1024 * 1024,
                    }
                ]
            }
        )

        self.assertTrue(router.is_loaded("qwen3:8b"))
        state = router.memory_state()
        self.assertEqual(state["loaded_models"], ["qwen3:8b"])
        self.assertEqual(state["vram_used_gb"], 3.0)
        self.assertEqual(state["free_vram_gb"], 5.0)

    def test_estimate_fit_allows_normal_model_and_rejects_premium_default(self) -> None:
        router = InferenceRouter(ROOT)
        normal = router.estimate_fit("qwen3:8b", 8192, concurrency=1)
        premium = router.estimate_fit("qwen3:30b-a3b-q4_K_M", 8192, concurrency=1)

        self.assertTrue(normal["fits"])
        self.assertEqual(normal["weight_class"], "normal")
        self.assertFalse(premium["fits"])
        self.assertEqual(premium["weight_class"], "premium")

    def test_validate_config_reports_missing_models_and_unreachable_llama_cpp(self) -> None:
        router = InferenceRouter(ROOT)
        router._routing = {
            "llama_cpp_servers": {
                "fast_lane": {
                    "base_url": "http://127.0.0.1:8180",
                    "models": ["qwen3:8b"],
                    "fallback_to_ollama": True,
                }
            },
            "chat_layer": {
                "model": "qwen3:8b",
                "fallback_models": ["qwen3:30b-a3b-q4_K_M"],
                "num_ctx": 8192,
            },
            "premium_models": ["qwen3:30b-a3b-q4_K_M"],
        }
        router.list_backends = MagicMock(
            return_value=[
                {
                    "name": "ollama",
                    "kind": "ollama",
                    "reachable": True,
                    "models": ["qwen3:8b"],
                },
                {
                    "name": "fast_lane",
                    "kind": "llama.cpp",
                    "reachable": False,
                    "models": [],
                    "backoff_until_sec": 120,
                },
            ]
        )

        report = router.validate_config()

        self.assertTrue(report["ok"])
        self.assertTrue(any("fast_lane" in item for item in report["warnings"]))
        self.assertTrue(any("qwen3:30b" in item for item in report["warnings"]))

    def test_explain_route_includes_backend_chain_fit_and_warnings(self) -> None:
        router = InferenceRouter(ROOT)
        router._routing = {
            "chat_layer": {
                "model": "qwen3:8b",
                "fallback_models": ["deepseek-r1:8b"],
                "num_ctx": 8192,
            }
        }
        router._model_map = {"qwen3:8b": "fast_lane"}
        router.list_backends = MagicMock(
            return_value=[
                {
                    "name": "ollama",
                    "kind": "ollama",
                    "reachable": True,
                    "models": ["deepseek-r1:8b"],
                },
                {
                    "name": "fast_lane",
                    "kind": "llama.cpp",
                    "reachable": False,
                    "models": [],
                    "backoff_until_sec": 0,
                },
            ]
        )
        router._read_ollama_ps_json = MagicMock(return_value={"models": [{"name": "deepseek-r1:8b"}]})

        explanation = router.explain_route(task_class="chat_layer")

        self.assertEqual(explanation["requested_model"], "qwen3:8b")
        self.assertEqual(explanation["selected_model"], "deepseek-r1:8b")
        self.assertEqual(explanation["backend"], "ollama")
        self.assertEqual(explanation["fallback_chain"], ["qwen3:8b", "deepseek-r1:8b"])
        self.assertTrue(explanation["installed"])
        self.assertTrue(explanation["loaded"])
        self.assertIn("estimated_fit", explanation)

    def test_chat_reports_fallback_chain_failure_when_all_backends_down(self) -> None:
        router = InferenceRouter(ROOT)
        router._server_declares_model = MagicMock(return_value=False)
        router._ollama = MagicMock()
        router._ollama.chat.side_effect = RuntimeError("backend unavailable")

        with self.assertRaises(RuntimeError) as ctx:
            router.chat(
                model="qwen3:8b",
                system_prompt="sys",
                user_prompt="hello",
                fallback_models=["deepseek-r1:8b"],
                retry_attempts=1,
            )
        message = str(ctx.exception)
        self.assertIn("qwen3:8b", message)
        self.assertIn("deepseek-r1:8b", message)


if __name__ == "__main__":
    unittest.main()
