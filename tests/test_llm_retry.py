from __future__ import annotations

import unittest

from tests.common import ROOT  # noqa: F401
from shared_tools.llm_retry import chat_with_self_fix_retry


class _FakeClient:
    def __init__(self, responses: list[str]) -> None:
        self._responses = list(responses)
        self.calls: list[dict[str, object]] = []

    def chat(self, **kwargs):  # type: ignore[no-untyped-def]
        self.calls.append(dict(kwargs))
        if self._responses:
            return self._responses.pop(0)
        return ""


class LlmRetryTests(unittest.TestCase):
    def test_self_fix_retry_corrects_after_validation_failure(self) -> None:
        client = _FakeClient(["not-json", '{"ok": "yes"}'])
        result = chat_with_self_fix_retry(
            client,
            model="qwen3:8b",
            system_prompt="return json",
            user_prompt="make payload",
            validator=lambda text: None if text.strip().startswith("{") else "must be json object",
            max_self_fix_attempts=2,
        )
        self.assertEqual(result.text, '{"ok": "yes"}')
        self.assertEqual(result.attempts_used, 2)
        self.assertTrue(result.corrected)
        self.assertTrue(result.validated)
        self.assertEqual(len(client.calls), 2)
        self.assertIn("failed validation", str(client.calls[1].get("user_prompt", "")).lower())

    def test_returns_last_output_when_validation_never_passes(self) -> None:
        client = _FakeClient(["bad-one", "bad-two"])
        result = chat_with_self_fix_retry(
            client,
            model="qwen3:8b",
            system_prompt="return json",
            user_prompt="make payload",
            validator=lambda _text: "still invalid",
            max_self_fix_attempts=2,
        )
        self.assertEqual(result.text, "bad-two")
        self.assertEqual(result.validation_error, "still invalid")
        self.assertEqual(result.attempts_used, 2)
        self.assertFalse(result.validated)

    def test_no_validator_uses_single_attempt(self) -> None:
        client = _FakeClient(["ready"])
        result = chat_with_self_fix_retry(
            client,
            model="qwen3:8b",
            system_prompt="x",
            user_prompt="y",
            max_self_fix_attempts=3,
        )
        self.assertEqual(result.text, "ready")
        self.assertEqual(result.attempts_used, 1)
        self.assertFalse(result.corrected)
        self.assertTrue(result.validated)

    def test_validator_exception_fails_open_without_crashing(self) -> None:
        client = _FakeClient(["output"])

        def _validator(_text: str) -> str | None:
            raise RuntimeError("validator blew up")

        result = chat_with_self_fix_retry(
            client,
            model="qwen3:8b",
            system_prompt="x",
            user_prompt="y",
            validator=_validator,
            max_self_fix_attempts=3,
        )
        self.assertEqual(result.text, "output")
        self.assertEqual(result.attempts_used, 1)
        self.assertIn("validator_exception", result.validation_error)
        self.assertFalse(result.validated)

    def test_retry_prompt_trims_large_validation_error_context(self) -> None:
        client = _FakeClient(["bad", '{"ok": true}'])
        long_error = "x" * 12000
        result = chat_with_self_fix_retry(
            client,
            model="qwen3:8b",
            system_prompt="return json",
            user_prompt="make payload",
            validator=lambda text: None if text.strip().startswith("{") else long_error,
            max_self_fix_attempts=2,
        )
        self.assertEqual(result.attempts_used, 2)
        second_prompt = str(client.calls[1].get("user_prompt", ""))
        self.assertLess(len(second_prompt), 12000)

    def test_zero_attempt_config_still_executes_one_attempt(self) -> None:
        client = _FakeClient(["result"])
        result = chat_with_self_fix_retry(
            client,
            model="qwen3:8b",
            system_prompt="sys",
            user_prompt="user",
            max_self_fix_attempts=0,
        )
        self.assertEqual(result.text, "result")
        self.assertEqual(result.attempts_used, 1)
        self.assertEqual(len(client.calls), 1)


if __name__ == "__main__":
    unittest.main()
