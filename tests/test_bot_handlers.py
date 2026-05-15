from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from bots import bot_runner, discord_bot, slack_bot, telegram_bot


class _FakeConversationStore:
    instances: list["_FakeConversationStore"] = []

    def __init__(self, _repo_root: Path, _uid: str) -> None:
        self.messages: list[tuple[str, str, str]] = []
        _FakeConversationStore.instances.append(self)

    def get(self, _conversation_id: str) -> dict:
        return {"messages": [{"role": "user", "content": "existing", "mode": "talk"}]}

    def add_message(self, conversation_id: str, role: str, content: str, *, mode: str = "talk") -> None:
        self.messages.append((conversation_id, role, content))


class _FakeOrchestrator:
    last_kwargs: dict = {}

    def __init__(self, _repo_root: Path) -> None:
        pass

    def conversation_reply(self, text: str, **kwargs):  # type: ignore[no-untyped-def]
        _FakeOrchestrator.last_kwargs = dict(kwargs)
        return f"reply:{text}"


class BotHandlerTests(unittest.TestCase):
    def setUp(self) -> None:
        _FakeConversationStore.instances.clear()
        _FakeOrchestrator.last_kwargs = {}

    def test_telegram_dispatch_routes_through_kernel_with_guest_scope(self) -> None:
        bot = telegram_bot.TelegramBot(Path("/tmp"), "token")
        mapping = {"oathweaver_user_id": "owner_1", "conversation_id": "conv_1"}

        with patch("shared_tools.conversation_store.ConversationStore", _FakeConversationStore), patch(
            "orchestrator.main.OathweaverOrchestrator", _FakeOrchestrator
        ):
            reply = bot._run_orchestrator(mapping, "hello telegram")

        self.assertEqual(reply, "reply:hello telegram")
        self.assertEqual(_FakeOrchestrator.last_kwargs.get("role_scope"), "guest")
        self.assertTrue(_FakeConversationStore.instances)
        recorded = _FakeConversationStore.instances[0].messages
        self.assertEqual(recorded[0][1], "user")
        self.assertEqual(recorded[-1][1], "assistant")

    def test_discord_dispatch_routes_through_kernel_with_guest_scope(self) -> None:
        bot = discord_bot.DiscordBot(Path("/tmp"), "token")
        mapping = {"oathweaver_user_id": "owner_1", "conversation_id": "conv_1"}

        with patch("shared_tools.conversation_store.ConversationStore", _FakeConversationStore), patch(
            "orchestrator.main.OathweaverOrchestrator", _FakeOrchestrator
        ):
            reply = bot._run_orchestrator(mapping, "hello discord")

        self.assertEqual(reply, "reply:hello discord")
        self.assertEqual(_FakeOrchestrator.last_kwargs.get("role_scope"), "guest")
        self.assertTrue(str(_FakeOrchestrator.last_kwargs.get("persona_override", "")).strip())

    def test_slack_enabled_config_is_ignored_without_crashing_runner(self) -> None:
        tmp = tempfile.TemporaryDirectory(prefix="slack_runner_")
        self.addCleanup(tmp.cleanup)
        repo_root = Path(tmp.name)
        started: list[str] = []

        class _FakeSlackBot:
            def __init__(self, _repo_root: Path, _bot_token: str, _app_token: str) -> None:
                pass

            def start(self) -> None:
                started.append("slack")

        with patch("bots.bot_runner.load_bot_config", return_value={
            "telegram": {"enabled": False, "bot_token": ""},
            "discord": {"enabled": False, "bot_token": ""},
            "slack": {"enabled": True, "bot_token": "xoxb", "app_token": "xapp"},
        }), patch("bots.slack_bot.SlackBot", _FakeSlackBot):
            with bot_runner._bots_lock:
                bot_runner._running_bots.clear()
            bot_runner.start_bots(repo_root)
            with bot_runner._bots_lock:
                self.assertEqual(len(bot_runner._running_bots), 1)
            self.assertEqual(started, ["slack"])

    def test_slack_dispatch_routes_through_kernel_with_guest_scope(self) -> None:
        bot = slack_bot.SlackBot(Path("/tmp"), "xoxb-token", "xapp-token")
        mapping = {"oathweaver_user_id": "owner_1", "conversation_id": "conv_1"}

        with patch("shared_tools.conversation_store.ConversationStore", _FakeConversationStore), patch(
            "orchestrator.main.OathweaverOrchestrator", _FakeOrchestrator
        ):
            reply = bot._run_orchestrator(mapping, "hello slack")

        self.assertEqual(reply, "reply:hello slack")
        self.assertEqual(_FakeOrchestrator.last_kwargs.get("role_scope"), "guest")
        self.assertTrue(_FakeConversationStore.instances)
        recorded = _FakeConversationStore.instances[0].messages
        self.assertEqual(recorded[0][1], "user")
        self.assertEqual(recorded[-1][1], "assistant")


if __name__ == "__main__":
    unittest.main()
