from __future__ import annotations

import re
from typing import TYPE_CHECKING

from flask import Blueprint, request, session

if TYPE_CHECKING:
    from web_gui.app_context import AppContext


def register_auth_routes(bp: Blueprint, ctx: AppContext) -> None:
    @bp.route("/api/auth/status", methods=["GET"])
    def auth_status() -> tuple[dict, int]:
        bootstrap = ctx.auth_bootstrap_state()
        profile = ctx.session_profile()
        return {
            "enabled": ctx.auth_enabled,
            "authenticated": profile is not None,
            "profile": ctx.public_profile(profile),
            "setup_required": bool(bootstrap.get("setup_required", False)),
            "setup_allowed": bool(bootstrap.get("setup_allowed", False)),
            "setup_message": str(bootstrap.get("setup_message", "")).strip(),
            "default_owner_username": "owner",
        }, 200

    @bp.route("/api/auth/login", methods=["POST"])
    def auth_login() -> tuple[dict, int]:
        if not ctx.auth_enabled:
            session.permanent = True
            session["authenticated"] = True
            session["user_id"] = ctx.owner_id
            return {
                "ok": True,
                "enabled": False,
                "authenticated": True,
                "profile": ctx.public_profile(ctx.owner_profile),
            }, 200
        bootstrap = ctx.auth_bootstrap_state()
        if bool(bootstrap.get("setup_required", False)):
            return {"ok": False, "error": "Owner account setup is required before login."}, 409
        payload = request.get_json(silent=True) or {}
        username = str(payload.get("username", "")).strip()
        password = str(payload.get("password", ""))
        client_ip = str(request.remote_addr or "")
        if ctx.login_limiter.is_locked(client_ip, username):
            return {"ok": False, "error": "Too many failed attempts. Please try again later."}, 429
        profile = ctx.auth_store.verify_login(username=username, password=password)
        if profile is None:
            ctx.login_limiter.record_failure(client_ip, username)
            return {"ok": False, "error": "Invalid username or password"}, 401
        ctx.login_limiter.record_success(client_ip, username)
        session.permanent = True
        session["authenticated"] = True
        session["user_id"] = str(profile.get("id", "")).strip()
        return {
            "ok": True,
            "enabled": True,
            "authenticated": True,
            "profile": ctx.public_profile(profile),
        }, 200

    @bp.route("/api/auth/setup-owner", methods=["POST"])
    def auth_setup_owner() -> tuple[dict, int]:
        if not ctx.auth_enabled:
            return {"ok": False, "error": "Owner setup API is disabled when auth is disabled."}, 400

        bootstrap = ctx.auth_bootstrap_state()
        if not bool(bootstrap.get("setup_required", False)):
            return {"ok": False, "error": "Owner account already exists."}, 409
        if not bool(bootstrap.get("setup_allowed", False)):
            message = str(bootstrap.get("setup_message", "")).strip() or "Owner setup is blocked."
            return {"ok": False, "error": message}, 409

        payload = request.get_json(silent=True) or {}
        username = str(payload.get("username", "")).strip().lower()
        password = str(payload.get("password", ""))
        confirm_password = str(payload.get("confirm_password", ""))

        if not re.fullmatch(r"[a-z0-9_-]{1,32}", username):
            return {"ok": False, "error": "Username must be 1-32 chars using letters, numbers, underscore, or hyphen."}, 400
        if len(password) < 4:
            return {"ok": False, "error": "Password must be at least 4 characters."}, 400
        if len(password) > 128:
            return {"ok": False, "error": "Password is too long."}, 400
        if password != confirm_password:
            return {"ok": False, "error": "Password confirmation does not match."}, 400

        owner = ctx.auth_store.ensure_owner(owner_password=password, owner_username=username)
        owner_id = str(owner.get("id", "")).strip()
        ctx.owner_profile = owner
        ctx.owner_id = owner_id
        session.permanent = True
        session["authenticated"] = True
        session["user_id"] = owner_id
        return {
            "ok": True,
            "enabled": True,
            "authenticated": True,
            "profile": ctx.public_profile(owner),
            "setup_required": False,
            "setup_allowed": False,
            "setup_message": "",
        }, 200

    @bp.route("/api/auth/logout", methods=["POST"])
    def auth_logout() -> tuple[dict, int]:
        session.clear()
        return {"ok": True}, 200
