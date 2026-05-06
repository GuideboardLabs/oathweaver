from __future__ import annotations

from typing import TYPE_CHECKING

from flask import Blueprint, request

from shared_tools.phase0 import normalize_domain
from web_gui.utils.request_utils import parse_optional_int

if TYPE_CHECKING:
    from web_gui.app_context import AppContext


def create_watchtower_blueprint(ctx: AppContext) -> Blueprint:
    bp = Blueprint('watchtower_routes', __name__)

    @bp.route('/api/watchtower/watches', methods=['GET'])
    def watchtower_list_watches() -> tuple[dict, int]:
        ctx.require_profile()
        wt = ctx.get_watchtower()
        return {"watches": wt.list_watches()}, 200

    @bp.route('/api/watchtower/watches', methods=['POST'])
    def watchtower_add_watch() -> tuple[dict, int]:
        ctx.require_profile()
        payload = request.get_json(silent=True) or {}
        wt = ctx.get_watchtower()
        domain = str(payload.get("domain", payload.get("profile", "general"))).strip()
        try:
            watch = wt.add_watch(
                topic=str(payload.get("topic", "")).strip(),
                profile=normalize_domain(domain),
                schedule=str(payload.get("schedule", "daily")).strip(),
                schedule_hour=int(payload.get("schedule_hour", 7)),
            )
        except ValueError as exc:
            return {"ok": False, "message": str(exc)}, 400
        watch["domain"] = str(watch.get("profile", "general")).strip()
        return {"ok": True, "watch": watch}, 200

    @bp.route('/api/watchtower/watches/<watch_id>', methods=['PUT'])
    def watchtower_update_watch(watch_id: str) -> tuple[dict, int]:
        ctx.require_profile()
        payload = request.get_json(silent=True) or {}
        if "domain" in payload and "profile" not in payload:
            payload["profile"] = normalize_domain(str(payload.get("domain", "general")))
        wt = ctx.get_watchtower()
        updated = wt.update_watch(watch_id, **{k: v for k, v in payload.items()})
        if updated is None:
            return {"ok": False, "message": "Watch not found."}, 404
        updated["domain"] = str(updated.get("profile", "general")).strip()
        return {"ok": True, "watch": updated}, 200

    @bp.route('/api/watchtower/watches/<watch_id>', methods=['DELETE'])
    def watchtower_delete_watch(watch_id: str) -> tuple[dict, int]:
        ctx.require_profile()
        wt = ctx.get_watchtower()
        ok = wt.delete_watch(watch_id)
        if not ok:
            return {"ok": False, "message": "Watch not found."}, 404
        return {"ok": True}, 200

    @bp.route('/api/watchtower/watches/<watch_id>/trigger', methods=['POST'])
    def watchtower_trigger_watch(watch_id: str) -> tuple[dict, int]:
        ctx.require_profile()
        wt = ctx.get_watchtower()
        try:
            result = wt.trigger_watch(watch_id)
        except ValueError as exc:
            return {"ok": False, "message": str(exc)}, 404
        return {"ok": True, "watch": result}, 200

    @bp.route('/api/panel/watchtower-research-cards', methods=['GET'])
    def panel_research_cards() -> tuple[dict, int]:
        ctx.require_profile()
        limit = parse_optional_int(request.args.get("limit"), default=50, minimum=1, maximum=200)
        wt = ctx.get_watchtower()
        cards = wt.list_research_cards(limit=limit)
        queued_cards = wt.list_cards(limit=limit)
        return {
            "research_cards": cards,
            "cards": cards,
            "unread_count": wt.unread_count(),
            "watchtower_cards": queued_cards,
            "watchtower_card_summary": wt.scout.card_store.summarize(),
        }, 200

    @bp.route('/api/watchtower/research-cards/<card_id>', methods=['GET'])
    def research_card_get(card_id: str) -> tuple[dict, int]:
        ctx.require_profile()
        wt = ctx.get_watchtower()
        row = wt.get_research_card(card_id)
        if row is None:
            return {"ok": False, "message": "Research card not found."}, 404
        return {"ok": True, "research_card": row}, 200

    @bp.route('/api/watchtower/research-cards/<card_id>/read', methods=['POST'])
    def mark_research_card_read(card_id: str) -> tuple[dict, int]:
        ctx.require_profile()
        wt = ctx.get_watchtower()
        ok = wt.mark_research_card_read(card_id)
        return {"ok": ok}, 200

    @bp.route('/api/watchtower/research-cards/<card_id>/unread', methods=['POST'])
    def mark_research_card_unread(card_id: str) -> tuple[dict, int]:
        ctx.require_profile()
        wt = ctx.get_watchtower()
        ok = wt.mark_research_card_unread(card_id)
        return {"ok": ok}, 200

    @bp.route('/api/watchtower/cards', methods=['GET'])
    def watchtower_list_cards() -> tuple[dict, int]:
        ctx.require_profile()
        wt = ctx.get_watchtower()
        limit = parse_optional_int(request.args.get("limit"), default=100, minimum=1, maximum=400)
        card_type = str(request.args.get("card_type", "")).strip()
        status = str(request.args.get("status", "")).strip()
        cards = wt.list_cards(limit=limit, card_type=card_type, status=status)
        return {"cards": cards, "summary": wt.scout.card_store.summarize()}, 200

    @bp.route('/api/watchtower/cards/<card_id>', methods=['GET'])
    def watchtower_get_card(card_id: str) -> tuple[dict, int]:
        ctx.require_profile()
        wt = ctx.get_watchtower()
        row = wt.get_card(card_id)
        if row is None:
            return {"ok": False, "message": "Card not found."}, 404
        return {"ok": True, "card": row}, 200

    @bp.route('/api/watchtower/cards/<card_id>/status', methods=['POST'])
    def watchtower_set_card_status(card_id: str) -> tuple[dict, int]:
        ctx.require_profile()
        wt = ctx.get_watchtower()
        payload = request.get_json(silent=True) or {}
        status = str(payload.get("status", "")).strip()
        note = str(payload.get("note", "")).strip()
        row = wt.set_card_status(card_id, status=status, note=note)
        if row is None:
            return {"ok": False, "message": "Card not found or invalid status."}, 404
        return {"ok": True, "card": row}, 200

    @bp.route('/api/watchtower/scan', methods=['POST'])
    def watchtower_scan_project_gaps() -> tuple[dict, int]:
        ctx.require_profile()
        wt = ctx.get_watchtower()
        payload = request.get_json(silent=True) or {}
        project = str(payload.get("project", "general")).strip() or "general"
        result = wt.scan_project_gaps(project=project)
        return {"ok": True, "scan": result}, 200

    return bp
