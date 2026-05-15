from __future__ import annotations

import io
import os
import shutil
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from tests.common import ensure_runtime


class WebGuiRouteCoverageTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        os.environ["OATHWEAVER_AUTH_ENABLED"] = "1"
        os.environ["OATHWEAVER_OWNER_USERNAME"] = "owner"
        os.environ["OATHWEAVER_OWNER_PASSWORD"] = "test-password"
        from web_gui import app as appmod

        cls.appmod = appmod

    def setUp(self) -> None:
        tmp = tempfile.TemporaryDirectory(prefix="web_gui_routes_")
        self.addCleanup(tmp.cleanup)
        self.repo_root = Path(tmp.name) / "repo"
        self.repo_root.mkdir(parents=True, exist_ok=True)
        ensure_runtime(self.repo_root)

        self._orig_root = self.appmod.ROOT
        self._orig_bg = self.appmod._ensure_background_services_started
        self.appmod.ROOT = self.repo_root
        self.appmod._ensure_background_services_started = lambda _app=None: None
        self.addCleanup(self._restore_app_globals)

        self.app = self.appmod.create_app()

    def _restore_app_globals(self) -> None:
        self.appmod.ROOT = self._orig_root
        self.appmod._ensure_background_services_started = self._orig_bg
        shutil.rmtree(self.repo_root.parent, ignore_errors=True)

    def _login(self, client) -> None:  # type: ignore[no-untyped-def]
        response = client.post(
            "/api/auth/login",
            json={"username": "owner", "password": "test-password"},
        )
        self.assertEqual(response.status_code, 200)
        payload = response.get_json() or {}
        self.assertTrue(bool(payload.get("ok", False)))

    def _create_conversation(self, client) -> str:  # type: ignore[no-untyped-def]
        response = client.post(
            "/api/conversations",
            json={"title": "Routes Coverage Thread", "kind": "general"},
        )
        self.assertEqual(response.status_code, 201)
        payload = response.get_json() or {}
        convo = payload.get("conversation") or {}
        conversation_id = str(convo.get("id", "")).strip()
        self.assertTrue(conversation_id)
        return conversation_id

    @staticmethod
    def _fake_pending_orch():
        class _FakePendingOrch:
            def pending_actions_data(self, limit: int = 20):
                _ = limit
                return [{"id": "pending_1", "kind": "reflection"}]

            def ignore_pending_action(self, action_id: str, reason: str = "") -> str:
                _ = reason
                return "pending action ignored" if action_id else "missing action id"

            def answer_pending_action(self, action_id: str, answer: str) -> str:
                return "reflection answered and closed" if action_id and answer else "invalid"

            def send_pending_action_to_codex(self, action_id: str, note: str = "") -> str:
                _ = note
                return "pending action routed to codex inbox" if action_id else "missing action id"

            def learn_outbox_one(self, target: str, thread_id: str, lane_hint: str | None = None) -> dict:
                _ = lane_hint
                return {"ok": bool(target and thread_id), "target": target, "thread_id": thread_id}

        return _FakePendingOrch()

    def _fake_message_orch(self):
        class _FakeProjectMemory:
            @staticmethod
            def get_facts(_project: str):
                return []

        class _FakeActivityStore:
            @staticmethod
            def rows():
                return []

        class _FakeMessageOrch:
            def __init__(self, repo_root: Path) -> None:
                self.repo_root = repo_root
                self.project_slug = "general"
                self.project_memory = _FakeProjectMemory()
                self.activity_store = _FakeActivityStore()

            def set_project(self, project: str) -> None:
                self.project_slug = project

            def refresh_project_facts(self, history=None, reset: bool = False) -> None:  # noqa: ANN001
                _ = history
                _ = reset

            def conversation_reply(self, text: str, **kwargs) -> str:  # noqa: ANN003
                _ = kwargs
                return f"talk:{text[:40]}"

            def handle_message(self, text: str, **kwargs) -> str:  # noqa: ANN003
                _ = kwargs
                return f"handled:{text[:40]}"

        return _FakeMessageOrch(self.repo_root)

    def test_auth_required_routes_return_401_when_unauthenticated(self) -> None:
        checks = [
            ("GET", "/api/conversations", None),
            ("POST", "/api/conversations/example/messages", {"content": "hello", "mode": "talk"}),
            ("GET", "/api/pending-actions", None),
            ("GET", "/api/projects", None),
            ("GET", "/api/owner/email-settings", None),
            ("POST", "/api/settings/web-mode", {"mode": "off"}),
            ("GET", "/api/panel/projects", None),
            ("GET", "/api/watchtower/watches", None),
            ("GET", "/api/family/profiles", None),
            ("POST", "/api/library/intake", None),
        ]
        with self.app.test_client() as client:
            for method, path, payload in checks:
                with self.subTest(method=method, path=path):
                    if method == "GET":
                        response = client.get(path)
                    elif path == "/api/library/intake":
                        response = client.post(path, data={}, content_type="multipart/form-data")
                    else:
                        response = client.post(path, json=payload)
                    self.assertEqual(response.status_code, 401)

    def test_representative_happy_paths_across_target_blueprints(self) -> None:
        with self.app.test_client() as client:
            self._login(client)
            conversation_id = self._create_conversation(client)

            list_conversations = client.get("/api/conversations")
            self.assertEqual(list_conversations.status_code, 200)

            # Message route happy path without model inference: make lane missing make_type triggers guard reply.
            make_guard = client.post(
                f"/api/conversations/{conversation_id}/messages",
                json={"content": "Build me a todo app", "mode": "make"},
            )
            self.assertEqual(make_guard.status_code, 200)

            self.assertEqual(client.get("/api/owner/email-settings").status_code, 200)
            self.assertEqual(client.get("/api/settings/fonts").status_code, 200)
            self.assertEqual(client.get("/api/watchtower/watches").status_code, 200)
            self.assertEqual(client.get("/api/panel/library").status_code, 200)
            self.assertEqual(client.get("/api/family/profiles").status_code, 200)

            project_upsert = client.post(
                "/api/projects/catalog",
                json={"project": "routes-demo", "description": "route coverage"},
            )
            self.assertEqual(project_upsert.status_code, 200)
            self.assertEqual(client.get("/api/projects/routes-demo/mode").status_code, 200)
            self.assertEqual(client.get("/api/panel/agent-graph").status_code, 200)

    def test_pending_actions_happy_and_failure_paths_with_mock_orchestrator(self) -> None:
        with patch("web_gui.app_context.AppContext.new_orch", autospec=True) as mocked_new_orch:
            mocked_new_orch.return_value = self._fake_pending_orch()
            with self.app.test_client() as client:
                self._login(client)
                listed = client.get("/api/pending-actions")
                self.assertEqual(listed.status_code, 200)

                ignored = client.post("/api/pending-actions/pending_1/ignore", json={"reason": "not now"})
                self.assertEqual(ignored.status_code, 200)

                bad_answer = client.post("/api/pending-actions/pending_1/answer", json={})
                self.assertEqual(bad_answer.status_code, 400)

                answered = client.post("/api/pending-actions/pending_1/answer", json={"answer": "ack"})
                self.assertEqual(answered.status_code, 200)

    def test_chat_message_talk_and_forage_paths_with_mock_orchestrator(self) -> None:
        with patch("web_gui.app_context.AppContext.new_orch", autospec=True) as mocked_new_orch, patch(
            "web_gui.routes.chat_messages.bg_summarize", return_value=None
        ), patch("web_gui.routes.chat_messages.bg_retitle", return_value=None):
            mocked_new_orch.return_value = self._fake_message_orch()
            with self.app.test_client() as client:
                self._login(client)
                conversation_id = self._create_conversation(client)

                talk = client.post(
                    f"/api/conversations/{conversation_id}/messages",
                    json={"content": "Explain the scheduler design", "mode": "talk"},
                )
                self.assertEqual(talk.status_code, 200)

                forage = client.post(
                    f"/api/conversations/{conversation_id}/messages",
                    json={"content": "Research compiler memory tradeoffs", "mode": "forage"},
                )
                self.assertEqual(forage.status_code, 200)

                make = client.post(
                    f"/api/conversations/{conversation_id}/messages",
                    json={"content": "Build release notes", "mode": "make", "make_type": "essay_long"},
                )
                self.assertEqual(make.status_code, 200)

    def test_chat_message_command_feedback_and_image_tool_paths(self) -> None:
        with patch("web_gui.app_context.AppContext.new_orch", autospec=True) as mocked_new_orch, patch(
            "web_gui.routes.chat_messages.bg_summarize", return_value=None
        ), patch("web_gui.routes.chat_messages.bg_retitle", return_value=None):
            mocked_new_orch.return_value = self._fake_message_orch()
            with self.app.test_client() as client:
                self._login(client)
                conversation_id = self._create_conversation(client)

                recap = client.post(
                    f"/api/conversations/{conversation_id}/messages",
                    json={"content": "/recap", "mode": "talk"},
                )
                self.assertEqual(recap.status_code, 200)

                convo = client.get(f"/api/conversations/{conversation_id}").get_json() or {}
                messages = (convo.get("conversation") or {}).get("messages") or []
                assistant = next((m for m in reversed(messages) if str(m.get("role", "")) == "assistant"), None)
                self.assertIsNotNone(assistant)
                message_id = str((assistant or {}).get("id", "")).strip()
                self.assertTrue(message_id)

                bad_feedback = client.post(
                    f"/api/conversations/{conversation_id}/messages/{message_id}/feedback",
                    json={"rating": "sideways"},
                )
                self.assertEqual(bad_feedback.status_code, 400)
                good_feedback = client.post(
                    f"/api/conversations/{conversation_id}/messages/{message_id}/feedback",
                    json={"rating": "up", "disregard": False},
                )
                self.assertEqual(good_feedback.status_code, 200)

                self.assertEqual(
                    client.post(
                        f"/api/conversations/{conversation_id}/image-tool/generate",
                        json={"prompt": "test"},
                    ).status_code,
                    410,
                )
                self.assertEqual(
                    client.post(
                        f"/api/conversations/{conversation_id}/image-tool/video-generate",
                        json={"prompt": "test"},
                    ).status_code,
                    410,
                )
                self.assertEqual(
                    client.post(
                        f"/api/conversations/{conversation_id}/image-tool/bg-enhance",
                        json={"prompt": "test"},
                    ).status_code,
                    410,
                )

    def test_chat_message_content_guard_blocks_and_returns_reason(self) -> None:
        with patch("web_gui.routes.chat_messages.check_content") as mocked_guard:
            mocked_guard.return_value = type("Guard", (), {"blocked": True, "reason": "Blocked for safety"})()
            with self.app.test_client() as client:
                self._login(client)
                conversation_id = self._create_conversation(client)
                response = client.post(
                    f"/api/conversations/{conversation_id}/messages",
                    json={"content": "forbidden content", "mode": "talk"},
                )
                self.assertEqual(response.status_code, 200)
                payload = response.get_json() or {}
                self.assertIn("Blocked for safety", str(payload.get("reply", "")))

    def test_representative_malformed_or_invalid_payloads_return_400(self) -> None:
        with self.app.test_client() as client:
            self._login(client)
            conversation_id = self._create_conversation(client)

            bad_cases = [
                (
                    "POST",
                    f"/api/conversations/{conversation_id}/messages",
                    {},
                    400,
                ),
                (
                    "PATCH",
                    f"/api/conversations/{conversation_id}",
                    {},
                    400,
                ),
                (
                    "POST",
                    "/api/pending-actions/pending_1/answer",
                    {},
                    400,
                ),
                (
                    "POST",
                    "/api/projects/catalog",
                    {},
                    400,
                ),
                (
                    "POST",
                    "/api/owner/bot-users",
                    {},
                    400,
                ),
                (
                    "POST",
                    "/api/settings/web-mode",
                    {"mode": "invalid-mode"},
                    400,
                ),
                (
                    "POST",
                    "/api/watchtower/watches",
                    {},
                    400,
                ),
                (
                    "POST",
                    "/api/family/profiles",
                    {},
                    400,
                ),
            ]

            for method, path, payload, expected in bad_cases:
                with self.subTest(method=method, path=path):
                    if method == "PATCH":
                        response = client.patch(path, json=payload)
                    else:
                        response = client.post(path, json=payload)
                    self.assertEqual(response.status_code, expected)

            empty_upload = client.post(
                "/api/library/intake",
                data={},
                content_type="multipart/form-data",
            )
            self.assertEqual(empty_upload.status_code, 400)

    def test_library_upload_happy_path(self) -> None:
        with self.app.test_client() as client:
            self._login(client)
            with patch("shared_tools.library_service.LibraryService.enqueue_ingest", return_value=None):
                response = client.post(
                    "/api/library/intake",
                    data={
                        "source_kind": "reference",
                        "files": (io.BytesIO(b"A short document for route coverage."), "coverage.txt"),
                    },
                    content_type="multipart/form-data",
                )
            self.assertEqual(response.status_code, 201)
            payload = response.get_json() or {}
            self.assertTrue(bool(payload.get("items")))


if __name__ == "__main__":
    unittest.main()
