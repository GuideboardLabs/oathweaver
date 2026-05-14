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


if __name__ == "__main__":
    unittest.main()
