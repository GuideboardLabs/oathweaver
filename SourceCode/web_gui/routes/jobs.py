from __future__ import annotations

from typing import TYPE_CHECKING

from flask import Blueprint, request

if TYPE_CHECKING:
    from web_gui.app_context import AppContext


def create_jobs_blueprint(ctx: AppContext) -> Blueprint:
    bp = Blueprint('job_routes', __name__)

    @bp.route('/api/jobs/<request_id>/cancel', methods=['POST'])
    def cancel_job(request_id: str) -> tuple[dict, int]:
        profile = ctx.require_profile()
        payload = request.get_json(silent=True) or {}
        expected_conversation = str(payload.get("conversation_id", "")).strip()
        row = ctx.job_manager.get(profile, request_id)
        if not isinstance(row, dict):
            return {"ok": False, "message": "Job not found."}, 404
        if expected_conversation and str(row.get("conversation_id", "")).strip() != expected_conversation:
            return {"ok": False, "message": "Job does not match this conversation."}, 400
        ok, summary = ctx.job_manager.request_cancel(profile, request_id)
        if not ok:
            return {"ok": False, "message": summary}, 400
        return {
            "ok": True,
            "message": "Cancel requested. The running job will stop at the next safe checkpoint.",
            "summary": summary,
            "request_id": request_id,
        }, 200

    @bp.route('/api/jobs/<request_id>', methods=['GET'])
    def get_job(request_id: str) -> tuple[dict, int]:
        profile = ctx.require_profile()
        row = ctx.job_manager.get(profile, request_id)
        if not isinstance(row, dict):
            return {"ok": False, "message": "Job not found.", "request_id": request_id}, 404
        payload = {
            "request_id": str(row.get("request_id", "")).strip(),
            "conversation_id": str(row.get("conversation_id", "")).strip(),
            "mode": str(row.get("mode", "")).strip(),
            "status": str(row.get("status", "")).strip(),
            "stage": str(row.get("stage", "")).strip(),
            "started_at": str(row.get("started_at", "")).strip(),
            "updated_at": str(row.get("updated_at", "")).strip(),
            "cancel_requested": bool(row.get("cancel_requested", False)),
            "summary_path": str(row.get("summary_path", "")).strip(),
            "raw_path": str(row.get("raw_path", "")).strip(),
            "web_stack": row.get("web_stack", {}) if isinstance(row.get("web_stack"), dict) else {},
            "events": list(row.get("events", []))[-24:] if isinstance(row.get("events", []), list) else [],
            "live_sources": list(row.get("live_sources", []))[-8:] if isinstance(row.get("live_sources", []), list) else [],
            "agent_tracker": row.get("agent_tracker") if isinstance(row.get("agent_tracker"), dict) else None,
        }
        summary = ctx.job_manager.progress_text(row)
        return {"ok": True, "job": payload, "summary": summary}, 200

    @bp.route('/api/jobs/<request_id>/events', methods=['GET'])
    def get_job_events(request_id: str) -> tuple[dict, int]:
        profile = ctx.require_profile()
        row = ctx.job_manager.get(profile, request_id)
        if not isinstance(row, dict):
            return {"ok": False, "message": "Job not found.", "request_id": request_id, "events": []}, 404
        events = list(row.get("events", []))
        return {"ok": True, "request_id": request_id, "events": events}, 200

    @bp.route('/api/jobs/<request_id>/stream', methods=['GET'])
    def stream_job(request_id: str) -> tuple[dict, int]:
        profile = ctx.require_profile()
        row = ctx.job_manager.get(profile, request_id)
        if not isinstance(row, dict):
            return {"ok": False, "message": "Job not found.", "request_id": request_id}, 404
        status = str(row.get("status", "")).strip()
        stage = str(row.get("stage", "")).strip()
        return {"ok": True, "request_id": request_id, "status": status, "stage": stage}, 200

    return bp
