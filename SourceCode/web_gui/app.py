from __future__ import annotations

import base64
import json
import mimetypes
import os
import re
import logging
import secrets
import sys
import time
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path
import threading
from threading import Lock
from typing import Any

from flask import Flask, abort, redirect, render_template, request, send_from_directory, session, url_for

ROOT = Path(__file__).resolve().parents[2]
SOURCE = ROOT / "SourceCode"
if str(SOURCE) not in sys.path:
    sys.path.insert(0, str(SOURCE))

from orchestrator.main import OathweaverOrchestrator
from shared_tools.content_guardrails import check_content
from shared_tools.conversation_store import ConversationStore
from shared_tools.family_auth import FamilyAuthStore
from shared_tools.project_pipeline import ProjectPipelineStore
from infra.persistence.migration_helpers import clear_structured_runtime_state
from web_gui.bootstrap import (
    background_state as _bootstrap_background_state,
    ensure_background_services_started,
    get_topic_engine,
    get_watchtower,
)

from shared_tools.email_notifier import (
    load_email_config,
    save_email_config,
    is_configured,
    is_dnd_active,
    format_subject,
    format_body,
    format_task_nudge_subject,
    format_task_nudge_body,
    send_notification_email,
)
from shared_tools.web_push import (
    get_user_settings as get_web_push_user_settings,
    send_notification as send_web_push_notification,
    subscribe_user as subscribe_web_push_user,
    unsubscribe_user as unsubscribe_web_push_user,
)

from web_gui.routes import (
    create_chat_blueprint,
    create_family_blueprint,
    create_jobs_blueprint,
    create_library_blueprint,
    create_projects_blueprint,
    create_system_blueprint,
    create_watchtower_blueprint,
)
from web_gui.services import JobManager, ForagingManager
from web_gui.utils.file_utils import (
    safe_path_in_roots as _safe_path_in_roots,
    safe_markdown_path as _safe_markdown_path,
    normalize_project_slug as _normalize_project_slug,
    safe_upload_name as _safe_upload_name,
    guess_mime_from_ext as _guess_mime_from_ext,
    read_text_file_preview as _read_text_file_preview,
)
from web_gui.utils.history_builders import (
    extract_talk_text as _extract_talk_text,
    build_talk_history as _build_talk_history,
    build_command_history as _build_command_history,
    build_fact_history as _build_fact_history,
)

GENERAL_PROJECT = "general"
DEFAULT_PROJECT = GENERAL_PROJECT

# ------------------------------------------------------------------
# Background service helpers
# ------------------------------------------------------------------
LOGGER = logging.getLogger(__name__)

_watchtower = None
_topic_engine = None


def _sync_bootstrap_state() -> None:
    global _watchtower, _topic_engine
    state = _bootstrap_background_state()
    _watchtower = state.get("watchtower")
    _topic_engine = state.get("topic_engine")


def _get_watchtower():
    engine = get_watchtower(ROOT)
    _sync_bootstrap_state()
    return engine


def _get_topic_engine():
    engine = get_topic_engine(ROOT)
    _sync_bootstrap_state()
    return engine


def _ensure_background_services_started(app: Flask | None = None) -> None:
    ensure_background_services_started(ROOT, app)
    _sync_bootstrap_state()


def _load_or_create_secret(path: Path) -> str:
    try:
        if path.exists():
            value = path.read_text(encoding="utf-8").strip()
            if value:
                return value
    except OSError:
        pass
    path.parent.mkdir(parents=True, exist_ok=True)
    value = secrets.token_urlsafe(48)
    path.write_text(value, encoding="utf-8")
    return value


def create_app() -> Flask:
    app = Flask(
        __name__,
        template_folder=str(Path(__file__).parent / "templates"),
        static_folder=str(Path(__file__).parent / "static"),
    )

    auth_enabled = str(os.environ.get("OATHWEAVER_AUTH_ENABLED", "1")).strip().lower() not in {"0", "false", "no"}
    auth_store = FamilyAuthStore(ROOT)
    owner_password = (
        str(os.environ.get("OATHWEAVER_OWNER_PASSWORD", "")).strip()
        or str(os.environ.get("OATHWEAVER_WEB_PASSWORD", "")).strip()
    )
    owner_username = str(os.environ.get("OATHWEAVER_OWNER_USERNAME", "owner")).strip() or "owner"
    try:
        owner_profile = auth_store.ensure_owner(owner_password=owner_password, owner_username=owner_username)
    except ValueError as exc:
        raise RuntimeError(
            "Oathweaver owner setup is incomplete. Set OATHWEAVER_OWNER_PASSWORD for first boot."
        ) from exc
    owner_id = str(owner_profile.get("id", "")).strip()

    session_secret = str(os.environ.get("OATHWEAVER_WEB_SECRET", "")).strip()
    if not session_secret:
        session_secret = _load_or_create_secret(ROOT / "Runtime" / "web" / "session_secret.txt")
    app.secret_key = session_secret
    app.config["SESSION_COOKIE_HTTPONLY"] = True
    app.config["SESSION_COOKIE_SAMESITE"] = "Lax"
    app.config["SESSION_COOKIE_SECURE"] = False
    _session_hours = max(1, int(os.environ.get("OATHWEAVER_SESSION_HOURS", "24")))
    app.config["PERMANENT_SESSION_LIFETIME"] = timedelta(hours=_session_hours)

    @app.before_request
    def _oathweaver_start_background_services() -> None:
        _ensure_background_services_started(app)

    panel_cache: dict[str, dict[str, Any]] = {}
    job_manager = JobManager()
    foraging_manager = ForagingManager()

    from web_gui.app_context import AppContext
    ctx = AppContext(
        root=ROOT,
        auth_store=auth_store,
        auth_enabled=auth_enabled,
        owner_profile=owner_profile,
        owner_id=owner_id,
        panel_cache=panel_cache,
        job_manager=job_manager,
        foraging_manager=foraging_manager,
    )

    @app.after_request
    def _no_cache(response):  # type: ignore[no-untyped-def]
        if request.path in {"/", "/manifest.webmanifest", "/service-worker.js"} or request.path.startswith("/static/"):
            response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
            response.headers["Pragma"] = "no-cache"
            response.headers["Expires"] = "0"
        return response

    @app.before_request
    def _auth_gate():  # type: ignore[no-untyped-def]
        if not ctx.auth_enabled:
            return None
        path = str(request.path or "")
        if path in {"/", "/manifest.webmanifest", "/service-worker.js"} or path.startswith("/static/"):
            return None
        if path in {
            "/api/health",
            "/api/auth/status",
            "/api/auth/login",
            "/api/auth/logout",
            "/api/settings/fonts",
        }:
            return None
        if ctx.session_profile() is not None:
            return None
        if path.startswith("/api/"):
            return {"error": "Authentication required"}, 401
        return redirect("/")

    app.register_blueprint(create_system_blueprint(ctx))

    app.register_blueprint(create_chat_blueprint(ctx))

    app.register_blueprint(create_jobs_blueprint(ctx))

    app.register_blueprint(create_library_blueprint(ctx))

    app.register_blueprint(create_watchtower_blueprint(ctx))

    app.register_blueprint(create_projects_blueprint(ctx))

    app.register_blueprint(create_family_blueprint(ctx))

    return app


app = create_app()


if __name__ == "__main__":
    # Start background services (watchtower, bots, etc.) before accepting connections
    # so bots connect immediately on startup rather than waiting for the first web request.
    _ensure_background_services_started(app)

    host = os.environ.get("OATHWEAVER_WEB_HOST", "0.0.0.0").strip() or "0.0.0.0"
    try:
        port = int(os.environ.get("OATHWEAVER_WEB_PORT", "5050").strip())
    except ValueError:
        port = 5050
    app.run(host=host, port=port, debug=False, threaded=True)
