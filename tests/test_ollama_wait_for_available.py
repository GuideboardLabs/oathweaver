from __future__ import annotations

import unittest
from unittest.mock import MagicMock

from tests.common import ROOT  # noqa: F401
from shared_tools.ollama_client import OllamaClient


class OllamaWaitForAvailableTests(unittest.TestCase):
    def test_chat_auto_enables_thinking_for_reasoning_models_by_default(self) -> None:
        client = OllamaClient()
        seen_payloads: list[dict] = []

        def fake_stream(payload: dict, *, timeout: int, idle_timeout_sec: int) -> str:
            seen_payloads.append(dict(payload))
            return "ok"

        client._post_json_stream_chat = MagicMock(side_effect=fake_stream)

        out = client.chat("qwen3:8b", "system", "user")

        self.assertEqual(out, "ok")
        self.assertEqual(seen_payloads[0].get("think"), True)

    def test_chat_respects_explicit_false_think_for_reasoning_models(self) -> None:
        client = OllamaClient()
        seen_payloads: list[dict] = []

        def fake_stream(payload: dict, *, timeout: int, idle_timeout_sec: int) -> str:
            seen_payloads.append(dict(payload))
            return "ok"

        client._post_json_stream_chat = MagicMock(side_effect=fake_stream)

        out = client.chat("qwen3:14b", "system", "user", think=False, num_predict=48)

        self.assertEqual(out, "ok")
        self.assertEqual(seen_payloads[0].get("think"), False)
        self.assertEqual(seen_payloads[0]["options"]["num_predict"], 48)

    def test_chat_respects_explicit_true_think_for_non_reasoning_models(self) -> None:
        client = OllamaClient()
        seen_payloads: list[dict] = []

        def fake_stream(payload: dict, *, timeout: int, idle_timeout_sec: int) -> str:
            seen_payloads.append(dict(payload))
            return "ok"

        client._post_json_stream_chat = MagicMock(side_effect=fake_stream)

        out = client.chat("qwen2.5-coder:7b", "system", "user", think=True)

        self.assertEqual(out, "ok")
        self.assertEqual(seen_payloads[0].get("think"), True)

    def test_wait_for_available_uses_tags_and_show_not_chat(self) -> None:
        client = OllamaClient()
        client._get_json = MagicMock(return_value={"models": [{"name": "qwen3:8b"}]})
        client._post_json = MagicMock(return_value={"details": {}})
        client.chat = MagicMock(side_effect=AssertionError("preflight must not call chat"))

        ok = client.wait_for_available(
            "qwen3:8b",
            fallback_models=["deepseek-r1:8b"],
            max_wait_sec=1,
            poll_interval_sec=1,
        )

        self.assertTrue(ok)
        client._get_json.assert_called_once_with("/api/tags", timeout=5)
        client._post_json.assert_called_once_with("/api/show", {"name": "qwen3:8b"}, timeout=5)
        client.chat.assert_not_called()

    def test_wait_for_available_uses_fallback_candidate_when_primary_missing(self) -> None:
        client = OllamaClient()
        client._get_json = MagicMock(return_value={"models": [{"name": "deepseek-r1:8b"}]})
        client._post_json = MagicMock(return_value={"details": {}})
        client.chat = MagicMock(side_effect=AssertionError("preflight must not call chat"))

        ok = client.wait_for_available(
            "qwen3:8b",
            fallback_models=["deepseek-r1:8b"],
            max_wait_sec=1,
            poll_interval_sec=1,
        )

        self.assertTrue(ok)
        client._post_json.assert_called_once_with("/api/show", {"name": "deepseek-r1:8b"}, timeout=5)
        client.chat.assert_not_called()

    def test_wait_for_available_sets_error_when_no_candidates_found(self) -> None:
        client = OllamaClient()
        client._get_json = MagicMock(return_value={"models": [{"name": "dolphin3:8b"}]})
        client._post_json = MagicMock(return_value={"details": {}})
        client.chat = MagicMock(side_effect=AssertionError("preflight must not call chat"))

        ok = client.wait_for_available(
            "qwen3:8b",
            fallback_models=["deepseek-r1:8b"],
            max_wait_sec=1,
            poll_interval_sec=1,
        )

        self.assertFalse(ok)
        self.assertIn("none of", str(client.last_wait_error).lower())
        client._post_json.assert_not_called()
        client.chat.assert_not_called()


if __name__ == "__main__":
    unittest.main()
