from __future__ import annotations

import socket
import unittest
from unittest.mock import MagicMock, patch

from tests.common import ROOT  # noqa: F401
from shared_tools.ollama_client import OllamaClient


class _FakeStreamResponse:
    def __init__(self, lines: list[bytes]) -> None:
        self._lines = list(lines)

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):  # type: ignore[no-untyped-def]
        return False

    def __iter__(self):
        return iter(self._lines)


class OllamaStreamWatchdogTests(unittest.TestCase):
    def test_stream_chat_accumulates_ndjson_chunks(self) -> None:
        client = OllamaClient()
        lines = [
            b'{"message":{"content":"Hello "},"done":false}\n',
            b'{"message":{"content":"world"},"done":true}\n',
        ]
        with patch("urllib.request.urlopen", return_value=_FakeStreamResponse(lines)):
            text = client._post_json_stream_chat({"model": "qwen3:8b", "stream": True, "messages": []}, timeout=30)
        self.assertEqual(text, "Hello world")

    def test_stream_chat_raises_on_idle_timeout(self) -> None:
        client = OllamaClient()
        with patch("urllib.request.urlopen", side_effect=socket.timeout("timed out")):
            with self.assertRaises(RuntimeError) as ctx:
                client._post_json_stream_chat(
                    {"model": "qwen3:8b", "stream": True, "messages": []},
                    timeout=30,
                    idle_timeout_sec=4,
                )
        self.assertIn("stalled", str(ctx.exception).lower())

    def test_chat_uses_stream_payload(self) -> None:
        client = OllamaClient()
        client._post_json_stream_chat = MagicMock(return_value="ok")  # type: ignore[method-assign]
        text = client.chat(
            model="qwen3:8b",
            system_prompt="sys",
            user_prompt="hello",
            retry_attempts=1,
            timeout=30,
        )
        self.assertEqual(text, "ok")
        payload = client._post_json_stream_chat.call_args.args[0]  # type: ignore[attr-defined]
        self.assertTrue(bool(payload.get("stream")))


if __name__ == "__main__":
    unittest.main()
