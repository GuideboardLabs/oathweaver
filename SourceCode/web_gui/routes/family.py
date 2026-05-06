from __future__ import annotations

from typing import TYPE_CHECKING

from flask import Blueprint, request

if TYPE_CHECKING:
    from web_gui.app_context import AppContext


def create_family_blueprint(ctx: AppContext) -> Blueprint:
    bp = Blueprint('family_routes', __name__)

    @bp.route('/api/family/profiles', methods=['GET'])
    def family_profiles() -> tuple[dict, int]:
        profile = ctx.require_profile()
        if not bool(profile.get("is_owner", False)):
            return {"ok": False, "error": "Only owner can list member profiles."}, 403
        rows = ctx.auth_store.list_profiles()
        return {"ok": True, "profiles": rows}, 200

    @bp.route('/api/family/profiles', methods=['POST'])
    def family_create_profile() -> tuple[dict, int]:
        profile = ctx.require_profile()
        if not bool(profile.get("is_owner", False)):
            return {"ok": False, "error": "Only owner can create member profiles."}, 403
        payload = request.get_json(silent=True) or {}
        username = str(payload.get("username", "")).strip()
        pin = str(payload.get("pin", payload.get("password", ""))).strip()
        display_name = str(payload.get("display_name", "")).strip()
        role = str(payload.get("role", "adult")).strip()
        color = str(payload.get("color", "")).strip()
        try:
            created = ctx.auth_store.create_profile(
                username=username,
                pin=pin,
                display_name=display_name,
                role=role,
                color=color,
            )
        except ValueError as exc:
            return {"ok": False, "error": str(exc)}, 400
        return {"ok": True, "profile": ctx.public_profile(created)}, 201

    @bp.route('/api/family/profiles/<profile_id>', methods=['PATCH'])
    def family_update_profile(profile_id: str) -> tuple[dict, int]:
        profile = ctx.require_profile()
        if not bool(profile.get("is_owner", False)):
            return {"ok": False, "error": "Only owner can edit member profiles."}, 403
        payload = request.get_json(silent=True) or {}
        username = payload.get("username", None)
        display_name = payload.get("display_name", None)
        role = payload.get("role", None)
        color = payload.get("color", None)
        pin = payload.get("pin", None)
        try:
            updated = ctx.auth_store.update_profile(
                user_id=profile_id,
                username=None if username is None else str(username).strip(),
                display_name=None if display_name is None else str(display_name).strip(),
                role=None if role is None else str(role).strip(),
                color=None if color is None else str(color).strip(),
                pin=None if pin is None else str(pin).strip(),
            )
        except ValueError as exc:
            return {"ok": False, "error": str(exc)}, 400
        return {"ok": True, "profile": ctx.public_profile(updated)}, 200

    return bp
