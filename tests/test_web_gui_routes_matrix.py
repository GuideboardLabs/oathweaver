from __future__ import annotations

import io
import os
import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest

from tests.common import ensure_runtime


@pytest.fixture()
def app_client():
    os.environ["OATHWEAVER_AUTH_ENABLED"] = "1"
    os.environ["OATHWEAVER_OWNER_USERNAME"] = "owner"
    os.environ["OATHWEAVER_OWNER_PASSWORD"] = "test-password"
    from web_gui import app as appmod

    tmp = tempfile.TemporaryDirectory(prefix="web_gui_matrix_")
    repo_root = Path(tmp.name) / "repo"
    repo_root.mkdir(parents=True, exist_ok=True)
    ensure_runtime(repo_root)

    orig_root = appmod.ROOT
    orig_bg = appmod._ensure_background_services_started
    appmod.ROOT = repo_root
    appmod._ensure_background_services_started = lambda _app=None: None
    app = appmod.create_app()

    with app.test_client() as client:
        yield client

    appmod.ROOT = orig_root
    appmod._ensure_background_services_started = orig_bg
    tmp.cleanup()


def _login(client) -> None:  # type: ignore[no-untyped-def]
    response = client.post("/api/auth/login", json={"username": "owner", "password": "test-password"})
    assert response.status_code == 200
    payload = response.get_json() or {}
    assert bool(payload.get("ok", False))


def _create_conversation(client) -> str:  # type: ignore[no-untyped-def]
    response = client.post("/api/conversations", json={"title": "Matrix Thread", "kind": "general"})
    assert response.status_code == 201
    payload = response.get_json() or {}
    conversation = payload.get("conversation") or {}
    convo_id = str(conversation.get("id", "")).strip()
    assert convo_id
    return convo_id


@pytest.mark.parametrize(
    ("method", "path", "payload"),
    [
        ("GET", "/api/conversations", None),
        ("POST", "/api/conversations", {"title": "x"}),
        ("GET", "/api/pending-actions", None),
        ("GET", "/api/projects", None),
        ("POST", "/api/projects/catalog", {"project": "demo"}),
        ("GET", "/api/owner/email-settings", None),
        ("POST", "/api/settings/web-mode", {"mode": "off"}),
        ("GET", "/api/panel/projects", None),
        ("GET", "/api/watchtower/watches", None),
        ("GET", "/api/family/profiles", None),
        ("GET", "/api/panel/library", None),
        ("POST", "/api/library/intake", None),
    ],
)
def test_auth_required_routes_reject_unauthenticated(app_client, method: str, path: str, payload):
    if method == "GET":
        response = app_client.get(path)
    elif path == "/api/library/intake":
        response = app_client.post(path, data={}, content_type="multipart/form-data")
    else:
        response = app_client.post(path, json=payload)
    assert response.status_code == 401


def test_auth_login_sets_samesite_strict_cookie(app_client) -> None:
    response = app_client.post("/api/auth/login", json={"username": "owner", "password": "test-password"})
    assert response.status_code == 200
    set_cookie = "; ".join(response.headers.getlist("Set-Cookie"))
    assert "SameSite=Strict" in set_cookie


def test_auth_login_failure_and_logout_flow(app_client) -> None:
    bad = app_client.post("/api/auth/login", json={"username": "owner", "password": "wrong"})
    assert bad.status_code == 401
    _login(app_client)
    out = app_client.post("/api/auth/logout")
    assert out.status_code == 200
    protected = app_client.get("/api/projects")
    assert protected.status_code == 401


@pytest.mark.skip(reason="Covered by dedicated route tests; broad matrix is unstable in this environment.")
def test_matrix_happy_paths_cover_all_target_blueprints(app_client) -> None:
    _login(app_client)
    conversation_id = _create_conversation(app_client)

    calls = [
        ("GET", "/api/auth/status", None),
        ("GET", "/api/conversations", None),
        ("GET", f"/api/conversations/{conversation_id}", None),
        ("POST", f"/api/conversations/{conversation_id}/read", None),
        ("GET", "/api/pending-actions", None),
        ("POST", "/api/pending-actions/pending_1/ignore", {"reason": "skip"}),
        ("GET", "/api/projects", None),
        ("POST", "/api/projects/catalog", {"project": "demo-alpha", "description": "demo"}),
        ("GET", "/api/projects/demo-alpha/mode", None),
        ("POST", "/api/projects/demo-alpha/mode", {"mode": "discovery", "target": "auto", "topic_type": "general"}),
        ("GET", "/api/owner/email-settings", None),
        ("GET", "/api/owner/bot-config", None),
        ("GET", "/api/owner/bot-users", None),
        ("GET", "/api/settings/fonts", None),
        ("GET", "/api/settings/morning-digest", None),
        ("GET", "/api/forage-cards", None),
        ("POST", "/api/settings/foraging", {"paused": True}),
        ("POST", "/api/settings/building", {"paused": True}),
        ("GET", "/api/panel/projects", None),
        ("GET", "/api/watchtower/watches", None),
        ("GET", "/api/panel/watchtower-research-cards", None),
        ("GET", "/api/family/profiles", None),
        ("GET", "/api/panel/library", None),
    ]
    for method, path, payload in calls:
        if method == "GET":
            response = app_client.get(path)
        elif payload is None:
            response = app_client.post(path)
        else:
            response = app_client.post(path, json=payload)
        assert response.status_code < 500


def test_matrix_failure_modes_cover_all_target_blueprints(app_client) -> None:
    _login(app_client)
    conversation_id = _create_conversation(app_client)

    checks = [
        app_client.post("/api/auth/login", json={"username": "", "password": ""}),
        app_client.patch(f"/api/conversations/{conversation_id}", json={}),
        app_client.post(f"/api/conversations/{conversation_id}/messages", json={}),
        app_client.post("/api/pending-actions/pending_1/answer", json={}),
        app_client.post("/api/projects/catalog", json={}),
        app_client.post("/api/projects/promote-branch", json={}),
        app_client.post("/api/owner/bot-users", json={}),
        app_client.post("/api/settings/web-mode", json={"mode": "invalid"}),
        app_client.post("/api/settings/external-tools-mode", json={"mode": "invalid"}),
        app_client.post("/api/auth/setup-owner", json={"username": "owner", "password": "x", "confirm_password": "x"}),
        app_client.post("/api/watchtower/watches", json={}),
        app_client.post("/api/family/profiles", json={}),
        app_client.post("/api/library/intake", data={}, content_type="multipart/form-data"),
        app_client.post("/api/system/reset-environment", json={"confirm": "NOPE"}),
    ]
    for response in checks:
        assert response.status_code in {400, 401, 404, 409}


def test_library_upload_happy_path_matrix(app_client) -> None:
    _login(app_client)
    with patch("shared_tools.library_service.LibraryService.enqueue_ingest", return_value=None):
        response = app_client.post(
            "/api/library/intake",
            data={
                "source_kind": "reference",
                "files": (io.BytesIO(b"test doc"), "matrix.txt"),
            },
            content_type="multipart/form-data",
        )
    assert response.status_code == 201



def test_conversation_file_routes_and_patch_paths(app_client) -> None:
    _login(app_client)
    conversation_id = _create_conversation(app_client)

    from web_gui import app as appmod
    root = Path(appmod.ROOT)
    notes = root / "Projects" / "demo-files" / "research_summaries" / "note.md"
    notes.parent.mkdir(parents=True, exist_ok=True)
    notes.write_text("# Heading\nBody", encoding="utf-8")
    data_json = root / "Projects" / "demo-files" / "implementation" / "data.json"
    data_json.parent.mkdir(parents=True, exist_ok=True)
    data_json.write_text('{"ok":true}', encoding="utf-8")
    data_bin = root / "Projects" / "demo-files" / "implementation" / "blob.bin"
    data_bin.write_bytes(b"\x00\x01\x02")

    md = app_client.get("/api/markdown", query_string={"path": str(notes)})
    assert md.status_code == 200
    text_file = app_client.get("/api/files/read", query_string={"path": str(data_json)})
    assert text_file.status_code == 200
    payload = text_file.get_json() or {}
    assert payload.get("render") == "json"
    binary_file = app_client.get("/api/files/read", query_string={"path": str(data_bin)})
    assert binary_file.status_code == 200

    patched = app_client.patch(
        f"/api/conversations/{conversation_id}",
        json={"title": "Renamed", "project": "demo-files", "topic_id": "", "selected_loras": "a,b,a"},
    )
    assert patched.status_code == 200
    deleted = app_client.delete(f"/api/conversations/{conversation_id}")
    assert deleted.status_code == 200
    missing = app_client.get(f"/api/conversations/{conversation_id}")
    assert missing.status_code == 404


def test_watchtower_crud_and_card_status_routes(app_client) -> None:
    _login(app_client)
    created = app_client.post(
        "/api/watchtower/watches",
        json={"topic": "AI regulation", "domain": "legal", "schedule": "daily", "schedule_hour": 8},
    )
    assert created.status_code == 200
    watch = (created.get_json() or {}).get("watch") or {}
    watch_id = str(watch.get("id", "")).strip()
    assert watch_id

    updated = app_client.put(f"/api/watchtower/watches/{watch_id}", json={"domain": "policy", "schedule_hour": 9})
    assert updated.status_code == 200
    triggered = app_client.post(f"/api/watchtower/watches/{watch_id}/trigger")
    assert triggered.status_code == 200
    cards = app_client.get("/api/watchtower/cards")
    assert cards.status_code == 200
    deleted = app_client.delete(f"/api/watchtower/watches/{watch_id}")
    assert deleted.status_code == 200


def test_panel_agent_graph_and_project_content_tree_routes(app_client) -> None:
    _login(app_client)
    from web_gui import app as appmod
    root = Path(appmod.ROOT)
    tree_root = root / "Projects" / "tree-demo" / "implementation" / "nested"
    tree_root.mkdir(parents=True, exist_ok=True)
    (tree_root / "file.md").write_text("x", encoding="utf-8")

    graph = app_client.get("/api/panel/agent-graph")
    assert graph.status_code == 200
    payload = graph.get_json() or {}
    assert "nodes" in payload

    content_tree = app_client.get("/api/projects/tree-demo/content-tree", query_string={"depth": 4, "nodes": 500})
    assert content_tree.status_code == 200
    tree_payload = content_tree.get_json() or {}
    assert bool(tree_payload.get("ok", False))


def test_project_promote_branch_and_owner_reset_environment(app_client) -> None:
    _login(app_client)
    source_id = _create_conversation(app_client)
    patch_project = app_client.patch(
        f"/api/conversations/{source_id}",
        json={"project": "source-branch", "topic_id": ""},
    )
    assert patch_project.status_code == 200

    promoted = app_client.post(
        "/api/projects/promote-branch",
        json={
            "source_conversation_id": source_id,
            "target_project": "target-branch",
            "mode": "clone",
            "copy_project_data": True,
            "description": "Promoted project",
        },
    )
    assert promoted.status_code == 200
    reset = app_client.post("/api/system/reset-environment", json={"confirm": "RESET"})
    assert reset.status_code == 200
    reset_payload = reset.get_json() or {}
    assert bool(reset_payload.get("ok", False))


def test_topics_crud_routes_and_subtopics(app_client) -> None:
    _login(app_client)
    listed = app_client.get("/api/topics")
    assert listed.status_code == 200
    created = app_client.post(
        "/api/topics",
        json={
            "name": "Battery Research",
            "type": "science",
            "description": "Focus on sodium-ion trends with concrete market, chemistry, and policy evidence.",
            "seed_question": "What changed in 2026?",
        },
    )
    assert created.status_code == 201
    topic = created.get_json() or {}
    topic_id = str(topic.get("id", "")).strip()
    assert topic_id

    fetched = app_client.get(f"/api/topics/{topic_id}")
    assert fetched.status_code == 200
    updated = app_client.put(f"/api/topics/{topic_id}", json={"description": "Updated desc"})
    assert updated.status_code == 200
    detail = app_client.get(f"/api/topics/{topic_id}/detail")
    assert detail.status_code == 200
    sub_created = app_client.post(
        f"/api/topics/{topic_id}/subtopics",
        json={
            "name": "Subtopic A",
            "type": "science",
            "description": "Subset coverage focused on cycle life, safety incidents, and production cost tradeoffs.",
            "seed_question": "What changed?",
        },
    )
    assert sub_created.status_code == 201
    sub_list = app_client.get(f"/api/topics/{topic_id}/subtopics")
    assert sub_list.status_code == 200
    deleted = app_client.delete(f"/api/topics/{topic_id}")
    assert deleted.status_code == 200
