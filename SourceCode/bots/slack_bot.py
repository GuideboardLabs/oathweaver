from __future__ import annotations

import logging
import threading
from pathlib import Path
from typing import Any

LOGGER = logging.getLogger(__name__)

_HISTORY_LIMIT = 20


class SlackBot(threading.Thread):
    def __init__(self, repo_root: Path, bot_token: str, app_token: str) -> None:
        super().__init__(name="oathweaver-slack-bot", daemon=True)
        self._repo_root = repo_root
        self._bot_token = bot_token
        self._app_token = app_token
        self._user_store: Any = None

    def run(self) -> None:
        try:
            from slack_bolt import App
            from slack_bolt.adapter.socket_mode import SocketModeHandler
        except ImportError:
            LOGGER.error(
                "slack-bolt is not installed. "
                "Install it with: pip install 'slack-bolt>=1.20'"
            )
            return

        from bots.bot_user_store import BotUserStore
        self._user_store = BotUserStore(self._repo_root)
        app = App(token=self._bot_token)

        @app.message("")
        def handle_message(message: dict[str, Any], say):  # type: ignore[no-untyped-def]
            user_id = str(message.get("user", "")).strip()
            text = str(message.get("text", "")).strip()
            if not user_id or not text:
                return
            mapping = self._user_store.get_mapping("slack", user_id)
            if mapping is None:
                LOGGER.info("Ignoring Slack message from unmapped user %s", user_id)
                return
            try:
                reply = self._run_orchestrator(mapping, text)
            except Exception:
                LOGGER.exception("Orchestrator error for Slack message.")
                reply = "Sorry, something went wrong processing your message."
            if str(reply).strip():
                say(reply)

        LOGGER.info("Slack bot started in Socket Mode.")
        SocketModeHandler(app, self._app_token).start()

    def _run_orchestrator(self, mapping: dict[str, Any], text: str) -> str:
        from orchestrator.main import OathweaverOrchestrator
        from shared_tools.conversation_store import ConversationStore

        uid = mapping["oathweaver_user_id"]
        conv_id = mapping["conversation_id"]

        store = ConversationStore(self._repo_root, uid)
        conv = store.get(conv_id)
        history: list[dict] = []
        if conv and isinstance(conv.get("messages"), list):
            history = conv["messages"][-_HISTORY_LIMIT:]

        store.add_message(conv_id, "user", text, mode="talk")

        orch = OathweaverOrchestrator(self._repo_root)
        reply = orch.conversation_reply(text, history=history, project="general", role_scope="guest")

        store.add_message(conv_id, "assistant", reply, mode="talk")
        return reply
