from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from flask import Blueprint, Flask

from tests.chat_route_testkit import FakeAppContext, FakeConversationStore
from tests.common import ensure_runtime  # noqa: F401  # ensure SourceCode on sys.path
from web_gui.routes.chat_messages import register_message_routes


class ChatNoImplicitRoutingTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmpdir = tempfile.TemporaryDirectory(prefix="oathweaver_chat_route_")
        self.repo_root = Path(self.tmpdir.name)
        ensure_runtime(self.repo_root)
        conversation = {
            "id": "c1",
            "title": "Test Conversation",
            "project": "general",
            "topic_id": "general",
            "messages": [],
            "has_unread": False,
            "selected_loras": [],
            "image_style": "realistic",
            "title_manually_set": False,
        }
        self.store = FakeConversationStore(conversation)
        self.ctx = FakeAppContext(self.repo_root, self.store)
        app = Flask(__name__)
        bp = Blueprint("chat_routes_for_test", __name__)
        register_message_routes(bp, self.ctx)
        app.register_blueprint(bp)
        self.client = app.test_client()

    def tearDown(self) -> None:
        self.tmpdir.cleanup()

    def test_chat_text_does_not_implicitly_route_to_make(self) -> None:
        response = self.client.post(
            "/api/conversations/c1/messages",
            json={"content": "make me an essay about cheese"},
        )
        self.assertEqual(response.status_code, 200)
        payload = response.get_json() or {}

        self.assertEqual(self.ctx.building_manager.register_calls, 0)
        self.assertEqual(self.ctx.foraging_manager.register_calls, 0)
        self.assertEqual(self.ctx._orch.handle_message_calls, 0)
        self.assertEqual(self.ctx._orch.conversation_reply_calls, 1)
        assistant_msg = payload.get("assistant_message") or {}
        self.assertEqual(assistant_msg.get("content"), "Talk-only response.")


if __name__ == "__main__":
    unittest.main()
