from __future__ import annotations

import logging
import threading
import time
from collections import deque
from pathlib import Path
from typing import Any

import requests

LOGGER = logging.getLogger(__name__)

_TG_API = "https://api.telegram.org/bot{token}/{method}"
_POLL_TIMEOUT = 25  # seconds for long-polling
_TYPING_INTERVAL = 4  # re-send typing action every N seconds
_HISTORY_LIMIT = 20  # conversation messages to pass as context
_PENDING_MAX = 20  # max unauthorized user IDs to remember

# Module-level store of recent unauthorized user IDs, read by the API
_pending_unauthorized: deque[dict[str, str]] = deque(maxlen=_PENDING_MAX)
_pending_lock = threading.Lock()


def get_pending_unauthorized() -> list[dict[str, str]]:
    with _pending_lock:
        return list(_pending_unauthorized)


class TelegramBot(threading.Thread):
    def __init__(self, repo_root: Path, token: str) -> None:
        super().__init__(name="oathweaver-telegram-bot", daemon=True)
        self._repo_root = repo_root
        self._token = token
        self._stop = threading.Event()
        # Lazy imports to avoid circular deps at startup
        self._user_store: Any = None
        self._auth_store: Any = None

    # ------------------------------------------------------------------ #
    # Thread entry point
    # ------------------------------------------------------------------ #

    def run(self) -> None:
        from bots.bot_user_store import BotUserStore
        from shared_tools.family_auth import FamilyAuthStore
        self._user_store = BotUserStore(self._repo_root)
        self._auth_store = FamilyAuthStore(self._repo_root)
        LOGGER.info("Telegram bot started.")
        offset = 0
        while not self._stop.is_set():
            try:
                updates = self._get_updates(offset)
                for update in updates:
                    offset = update["update_id"] + 1
                    threading.Thread(
                        target=self._handle_update,
                        args=(update,),
                        daemon=True,
                    ).start()
            except Exception:
                LOGGER.exception("Telegram polling error; retrying in 5s.")
                self._stop.wait(5)

    def stop(self) -> None:
        self._stop.set()

    # ------------------------------------------------------------------ #
    # Update handling
    # ------------------------------------------------------------------ #

    def _handle_update(self, update: dict[str, Any]) -> None:
        msg = update.get("message") or update.get("edited_message") or {}
        if not msg:
            return
        chat_id = msg.get("chat", {}).get("id")
        from_info = msg.get("from") or {}
        user_id = str(from_info.get("id", "")).strip()
        text = str(msg.get("text") or "").strip()

        if not chat_id or not text:
            return

        mapping = self._user_store.get_mapping("telegram", user_id)
        if not mapping:
            username = from_info.get("username") or from_info.get("first_name") or user_id
            with _pending_lock:
                # Avoid duplicates
                existing_ids = {p["platform_user_id"] for p in _pending_unauthorized}
                if user_id not in existing_ids:
                    _pending_unauthorized.append({
                        "platform": "telegram",
                        "platform_user_id": user_id,
                        "platform_username": username,
                    })
            self._send_message(chat_id, "Sorry, you're not authorized to use this bot.")
            return

        # Typing indicator runs in a side thread until we're done
        stop_typing = threading.Event()
        typing_thread = threading.Thread(
            target=self._typing_loop, args=(chat_id, stop_typing), daemon=True
        )
        typing_thread.start()

        try:
            reply = self._run_orchestrator(mapping, text)
        except Exception:
            LOGGER.exception("Orchestrator error for Telegram message.")
            reply = "Sorry, something went wrong processing your message."
        finally:
            stop_typing.set()

        for chunk in _chunk_text(reply, 4096):
            self._send_message(chat_id, chunk)

    def _run_orchestrator(self, mapping: dict[str, Any], text: str) -> str:
        from shared_tools.conversation_store import ConversationStore
        from orchestrator.main import OathweaverOrchestrator

        uid = mapping["oathweaver_user_id"]
        conv_id = mapping["conversation_id"]

        store = ConversationStore(self._repo_root, uid)
        conv = store.get(conv_id)
        history: list[dict] = []
        if conv and isinstance(conv.get("messages"), list):
            history = conv["messages"][-_HISTORY_LIMIT:]

        store.add_message(conv_id, "user", text, mode="talk")

        orch = OathweaverOrchestrator(self._repo_root)
        reply = orch.conversation_reply(text, history=history, project="general")

        store.add_message(conv_id, "assistant", reply, mode="talk")
        return reply

    # ------------------------------------------------------------------ #
    # Telegram API helpers
    # ------------------------------------------------------------------ #

    def _get_updates(self, offset: int) -> list[dict[str, Any]]:
        data = self._call("getUpdates", {
            "offset": offset,
            "timeout": _POLL_TIMEOUT,
            "allowed_updates": ["message", "edited_message"],
        })
        return data.get("result") or []

    def _send_message(self, chat_id: int | str, text: str) -> None:
        try:
            self._call("sendMessage", {"chat_id": chat_id, "text": text})
        except Exception:
            LOGGER.exception("Failed to send Telegram message.")

    def _send_chat_action(self, chat_id: int | str, action: str = "typing") -> None:
        try:
            self._call("sendChatAction", {"chat_id": chat_id, "action": action})
        except Exception:
            LOGGER.debug("Telegram chat action failed for %s.", chat_id, exc_info=True)

    def _typing_loop(self, chat_id: int | str, stop: threading.Event) -> None:
        self._send_chat_action(chat_id)
        while not stop.wait(_TYPING_INTERVAL):
            self._send_chat_action(chat_id)

    def _call(self, method: str, payload: dict[str, Any] | None = None) -> dict[str, Any]:
        url = _TG_API.format(token=self._token, method=method)
        resp = requests.post(url, json=payload or {}, timeout=_POLL_TIMEOUT + 5)
        resp.raise_for_status()
        return resp.json()


# ------------------------------------------------------------------ #
# Utilities
# ------------------------------------------------------------------ #

def _chunk_text(text: str, limit: int) -> list[str]:
    if len(text) <= limit:
        return [text]
    chunks: list[str] = []
    while text:
        if len(text) <= limit:
            chunks.append(text)
            break
        # Try to split on a paragraph boundary
        split_at = text.rfind("\n\n", 0, limit)
        if split_at == -1:
            split_at = text.rfind("\n", 0, limit)
        if split_at == -1:
            split_at = limit
        chunks.append(text[:split_at].strip())
        text = text[split_at:].strip()
    return [c for c in chunks if c]
