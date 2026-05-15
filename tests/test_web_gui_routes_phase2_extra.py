from __future__ import annotations

import os
import tempfile
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from tests.common import ensure_runtime


class _FakeActivityStore:
    def __init__(self, repo_root: Path) -> None:
        self._summary = repo_root / "Projects" / "demo" / "implementation" / "20260514_120000_status.md"
        self._summary.parent.mkdir(parents=True, exist_ok=True)
        self._summary.write_text("summary", encoding="utf-8")

    def rows(self):
        return [
            {
                "ts": "2026-05-14T00:00:00+00:00",
                "actor": "builder",
                "event": "routed",
                "details": {"project": "demo", "lane": "research"},
            },
            {
                "ts": "2026-05-14T00:10:00+00:00",
                "actor": "builder",
                "event": "make_deliverable_written",
                "details": {
                    "project": "demo",
                    "make_type": "essay_long",
                    "summary_path": str(self._summary),
                    "request_id": "req_1",
                    "topic": "Status",
                },
            },
        ]


class _FakeHandoffQueue:
    @staticmethod
    def monitor_threads(limit: int = 500):
        _ = limit
        return [
            {
                "id": "h1",
                "project": "demo",
                "status": "ready_for_ingest",
                "created_at": "2026-05-14T00:20:00+00:00",
                "outbox_path": "Runtime/handoffs/outbox/demo.jsonl",
            }
        ]


class _FakeReflectionEngine:
    @staticmethod
    def list_open(limit: int = 20):
        _ = limit
        return [{"id": "r1", "status": "open"}]

    @staticmethod
    def list_history(limit: int = 80):
        _ = limit
        return [{"id": "r0", "status": "closed"}]

    @staticmethod
    def count_open() -> int:
        return 1


class _FakeLearningEngine:
    @staticmethod
    def list_lessons(lane=None, limit: int = 25, sort_by: str = "newest"):
        _ = lane
        _ = limit
        _ = sort_by
        return [{"id": "l1", "policy_blocked": False}]

    @staticmethod
    def approve_lesson(lesson_id: str, approved_by: str):
        _ = approved_by
        return {"id": lesson_id, "policy_blocked": False}

    @staticmethod
    def reject_lesson(lesson_id: str, rejected_by: str):
        _ = rejected_by
        return {"id": lesson_id}

    @staticmethod
    def expire_lesson(lesson_id: str):
        return {"id": lesson_id}

    @staticmethod
    def count_lessons() -> int:
        return 3


class _FakeApprovalGate:
    @staticmethod
    def list_action_proposals(limit: int = 50):
        _ = limit
        return [{"id": "p1"}]

    @staticmethod
    def execute_proposal(proposal_id: str, _root: Path):
        return {"ok": bool(proposal_id), "message": "done"}

    @staticmethod
    def decide(proposal_id: str, approved: bool = False):
        _ = approved
        return bool(proposal_id)


class _FakeWebEngine:
    @staticmethod
    def set_mode(mode: str) -> str:
        return mode

    @staticmethod
    def list_pending(limit: int = 500):
        _ = limit
        return []

    @staticmethod
    def get_mode() -> str:
        return "ask"


class _FakeExternalMode:
    def __init__(self) -> None:
        self._mode = "ask"

    def get_mode(self) -> str:
        return self._mode


class _FakeOrch:
    def __init__(self, repo_root: Path) -> None:
        self.repo_root = repo_root
        self.project_slug = "general"
        self.activity_store = _FakeActivityStore(repo_root)
        self.handoff_queue = _FakeHandoffQueue()
        self.reflection_engine = _FakeReflectionEngine()
        self.learning_engine = _FakeLearningEngine()
        self.approval_gate = _FakeApprovalGate()
        self.web_engine = _FakeWebEngine()
        self.external_tools_settings = _FakeExternalMode()
        self.external_request_store = SimpleNamespace(list_open=lambda limit=500: [])

    def set_external_tools_mode(self, mode: str) -> str:
        self.external_tools_settings._mode = mode
        return "ok"

    @staticmethod
    def pending_actions_data(limit: int = 20):
        _ = limit
        return [{"id": "pending_1"}]


def _login(client) -> None:
    response = client.post("/api/auth/login", json={"username": "owner", "password": "test-password"})
    assert response.status_code == 200


def test_projects_panel_and_settings_routes_with_mock_orchestrator() -> None:
    os.environ["OATHWEAVER_AUTH_ENABLED"] = "1"
    os.environ["OATHWEAVER_OWNER_USERNAME"] = "owner"
    os.environ["OATHWEAVER_OWNER_PASSWORD"] = "test-password"
    from web_gui import app as appmod

    tmp = tempfile.TemporaryDirectory(prefix="web_gui_phase2_extra_")
    repo_root = Path(tmp.name) / "repo"
    repo_root.mkdir(parents=True, exist_ok=True)
    ensure_runtime(repo_root)
    for db_path in (repo_root / "Runtime" / "state").glob("*.db*"):
        db_path.unlink(missing_ok=True)

    orig_root = appmod.ROOT
    orig_bg = appmod._ensure_background_services_started
    appmod.ROOT = repo_root
    appmod._ensure_background_services_started = lambda _app=None: None
    app = appmod.create_app()

    try:
        fake_orch = _FakeOrch(repo_root)
        class _FakeHttpResp:
            def __init__(self, status: int = 200) -> None:
                self.status = status

            def __enter__(self):
                return self

            def __exit__(self, exc_type, exc, tb):
                _ = exc_type
                _ = exc
                _ = tb
                return False

        with patch("web_gui.app_context.AppContext.new_orch", autospec=True, return_value=fake_orch), patch(
            "web_gui.app_context.AppContext.orch_for", autospec=True, return_value=fake_orch
        ), patch("web_gui.routes.system_health.urllib.request.urlopen", return_value=_FakeHttpResp(200)):
            with app.test_client() as client:
                _login(client)

                assert client.get("/").status_code == 200
                assert client.get("/manifest.webmanifest").status_code == 200
                assert client.get("/service-worker.js").status_code == 200
                assert client.get("/api/health").status_code == 200
                assert client.get("/api/foraging/state").status_code == 200
                assert client.get("/api/research/state").status_code == 200
                assert client.get("/api/panel/status").status_code == 200

                assert client.get("/api/action-proposals").status_code == 200
                assert client.post("/api/action-proposals/p1/approve").status_code == 200
                assert client.post("/api/action-proposals/p1/reject").status_code == 200

                assert client.get("/api/projects").status_code == 200
                assert client.post("/api/projects/catalog", json={"project": "demo", "description": "x"}).status_code == 200
                assert client.get("/api/projects/demo/details").status_code == 200
                assert client.get("/api/projects/demo/make_outputs").status_code == 200

                assert client.get("/api/panel/reflections").status_code == 200
                assert client.get("/api/panel/reflections-history").status_code == 200
                assert client.get("/api/panel/lessons").status_code == 200
                assert client.post("/api/lessons/l1/approve").status_code == 200
                assert client.post("/api/lessons/l1/reject").status_code == 200
                assert client.post("/api/lessons/l1/expire").status_code == 200
                assert client.get("/api/panel/handoffs").status_code == 200
                assert client.get("/api/panel/outbox").status_code == 200
                assert client.get("/api/panel/projects").status_code == 200
                assert client.get("/api/panel/foraging").status_code == 200
                assert client.get("/api/panel/building").status_code == 200

                assert client.post("/api/settings/web-mode", json={"mode": "bad"}).status_code == 400
                assert client.post("/api/settings/web-mode", json={"mode": "ask"}).status_code == 200
                assert client.post("/api/settings/external-tools-mode", json={"mode": "bad"}).status_code == 400
                assert client.post("/api/settings/external-tools-mode", json={"mode": "auto"}).status_code == 200
                assert client.post("/api/settings/foraging", json={"paused": True}).status_code == 200
                assert client.post("/api/settings/building", json={"paused": True}).status_code == 200
                assert client.get("/api/settings/web-push").status_code == 200
                assert client.post("/api/settings/web-push/unsubscribe", json={"endpoint": ""}).status_code == 200
                assert client.post("/api/settings/web-push/test").status_code == 400
                assert client.get("/api/settings/fonts").status_code == 200

                assert client.get("/api/owner/email-settings").status_code == 200
                assert client.post("/api/owner/email-settings", json={"notification_email": "owner@example.com"}).status_code == 200
                assert client.post("/api/owner/email-settings/test", json={}).status_code == 400
                assert client.get("/api/owner/bot-config").status_code == 200
                assert client.post("/api/owner/bot-config", json={"telegram": {"enabled": False}}).status_code == 200
                assert client.get("/api/owner/bot-users").status_code == 200
                assert client.post("/api/owner/bot-users", json={}).status_code == 400
                assert client.get("/api/owner/bot-users/pending").status_code == 200
                assert client.get("/api/memory/topics").status_code == 200
                assert client.get("/api/memory/topics/missing").status_code == 404
                assert client.post("/api/memory/reviews/missing/answer", json={"accepted": False}).status_code == 404
                assert client.post("/api/system/reset-environment", json={"confirm": "NOPE"}).status_code == 400

                assert client.get("/api/watchtower/watches").status_code == 200
                assert client.get("/api/watchtower/cards").status_code == 200
                assert client.get("/api/panel/watchtower-research-cards").status_code == 200
                assert client.get("/api/watchtower/research-cards/missing").status_code == 404
                assert client.post("/api/watchtower/research-cards/missing/read").status_code == 200

                companion_dir = repo_root / "Images" / "HomePageCompanion"
                companion_dir.mkdir(parents=True, exist_ok=True)
                (companion_dir / "fox.png").write_bytes(b"png")
                assert client.get("/api/home/companion-images").status_code == 200
                assert client.get("/api/home/companion-images/fox.png").status_code == 200
                assert client.get("/api/home/companion-images/missing.png").status_code == 404

                assert client.get("/api/family/profiles").status_code == 200
                assert client.post("/api/family/profiles", json={}).status_code == 400

                assert client.get("/api/jobs/missing").status_code == 404
                assert client.get("/api/jobs/missing/events").status_code == 404
                assert client.get("/api/jobs/missing/stream").status_code == 404
                assert client.post("/api/jobs/missing/cancel", json={}).status_code == 404
    finally:
        appmod.ROOT = orig_root
        appmod._ensure_background_services_started = orig_bg
        tmp.cleanup()


def test_auth_setup_owner_validation_and_success_flow() -> None:
    os.environ["OATHWEAVER_AUTH_ENABLED"] = "1"
    os.environ.pop("OATHWEAVER_OWNER_PASSWORD", None)
    os.environ.pop("OATHWEAVER_WEB_PASSWORD", None)
    os.environ["OATHWEAVER_OWNER_USERNAME"] = "owner"
    from web_gui import app as appmod

    tmp = tempfile.TemporaryDirectory(prefix="web_gui_auth_setup_")
    repo_root = Path(tmp.name) / "repo"
    repo_root.mkdir(parents=True, exist_ok=True)
    ensure_runtime(repo_root)
    os.environ.pop("OATHWEAVER_OWNER_PASSWORD", None)
    os.environ.pop("OATHWEAVER_WEB_PASSWORD", None)

    orig_root = appmod.ROOT
    orig_bg = appmod._ensure_background_services_started
    appmod.ROOT = repo_root
    appmod._ensure_background_services_started = lambda _app=None: None
    app = appmod.create_app()

    try:
        with app.test_client() as client:
            status = client.get("/api/auth/status")
            assert status.status_code == 200
            status_payload = status.get_json() or {}
            assert bool(status_payload.get("setup_required", False))

            bad_user = client.post(
                "/api/auth/setup-owner",
                json={"username": "BAD SPACE", "password": "abcd", "confirm_password": "abcd"},
            )
            assert bad_user.status_code == 400

            short_pw = client.post(
                "/api/auth/setup-owner",
                json={"username": "owner", "password": "abc", "confirm_password": "abc"},
            )
            assert short_pw.status_code == 400

            mismatch = client.post(
                "/api/auth/setup-owner",
                json={"username": "owner", "password": "abcd", "confirm_password": "zzzz"},
            )
            assert mismatch.status_code == 400

            created = client.post(
                "/api/auth/setup-owner",
                json={"username": "owner", "password": "secure-pass", "confirm_password": "secure-pass"},
            )
            assert created.status_code == 200

            relogin = client.post("/api/auth/logout")
            assert relogin.status_code == 200
            good_login = client.post(
                "/api/auth/login",
                json={"username": "owner", "password": "secure-pass"},
            )
            assert good_login.status_code == 200
    finally:
        appmod.ROOT = orig_root
        appmod._ensure_background_services_started = orig_bg
        tmp.cleanup()
