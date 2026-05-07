from __future__ import annotations

import mimetypes
import tempfile
from pathlib import Path
from typing import TYPE_CHECKING, Any

from flask import Blueprint, abort, request, send_from_directory

from shared_tools.document_ingestion import extract_text
from web_gui.chat_helpers import ALLOWED_DOC_EXT, ALLOWED_DOC_MIME, ATTACHMENT_MAX_DOC_BYTES
from web_gui.utils.file_utils import safe_upload_name as _safe_upload_name

if TYPE_CHECKING:
    from web_gui.app_context import AppContext


def create_library_blueprint(ctx: AppContext) -> Blueprint:
    bp = Blueprint("library_routes", __name__)

    def _prepare_temp_upload(profile: dict[str, Any], file_obj: Any) -> tuple[Path | None, str, str, str]:
        source_name = _safe_upload_name(getattr(file_obj, "filename", "") or "document")
        mime = str(getattr(file_obj, "mimetype", "") or "").split(";")[0].strip().lower()
        ext = Path(source_name).suffix.lower()
        if ext not in ALLOWED_DOC_EXT and mime not in ALLOWED_DOC_MIME:
            return None, source_name, mime, f"Unsupported document type: {source_name}"
        blob = file_obj.read(ATTACHMENT_MAX_DOC_BYTES + 1)
        if len(blob) > ATTACHMENT_MAX_DOC_BYTES:
            return None, source_name, mime, f"Document too large: {source_name}"
        if not blob:
            return None, source_name, mime, f"Document is empty: {source_name}"
        tmp_dir = ctx.repo_root_for_profile(profile) / "Runtime" / "library" / "tmp"
        tmp_dir.mkdir(parents=True, exist_ok=True)
        guessed_ext = ext
        if not guessed_ext and mime:
            guessed_ext = (mimetypes.guess_extension(mime) or "").lower()
        with tempfile.NamedTemporaryFile(prefix="library_", suffix=guessed_ext, dir=tmp_dir, delete=False) as handle:
            handle.write(blob)
            temp_path = Path(handle.name)
        return temp_path, source_name, mime, ""

    @bp.get("/api/panel/library")
    def panel_library() -> tuple[dict[str, Any], int]:
        from web_gui.utils.request_utils import parse_optional_int

        profile = ctx.require_profile()
        service = ctx.library_service_for(profile)
        limit = parse_optional_int(request.args.get("limit"), default=120, minimum=1, maximum=250)
        return service.panel_payload(limit=limit), 200

    @bp.post("/api/library/intake")
    def library_intake() -> tuple[dict[str, Any], int]:
        profile = ctx.require_profile()
        service = ctx.library_service_for(profile)
        files = request.files.getlist("files")
        if not files:
            return {"error": "At least one file is required."}, 400

        source_kind = str(request.form.get("source_kind", "general")).strip().lower() or "general"
        title_override = str(request.form.get("title", "")).strip()
        topic_id = str(request.form.get("topic_id", "")).strip()
        project_slug = str(request.form.get("project_slug", "")).strip()
        domain = str(request.form.get("domain", "")).strip().lower()
        rows: list[dict[str, Any]] = []
        errors: list[str] = []

        for idx, file_obj in enumerate(files):
            temp_path, source_name, mime, error_text = _prepare_temp_upload(profile, file_obj)
            if error_text:
                errors.append(error_text)
                continue
            assert temp_path is not None
            try:
                item = service.intake_file(
                    temp_path,
                    source_name=source_name,
                    mime=mime,
                    source_kind=source_kind,
                    title=title_override if len(files) == 1 or idx == 0 else "",
                    topic_id=topic_id,
                    project_slug=project_slug,
                    domain=domain,
                    source_origin="manual_upload",
                    conversation_id="",
                )
                selected_topic_id = topic_id
                if not selected_topic_id:
                    preview_text = extract_text(Path(str(item.get("source_path", "")).strip()), mime)
                    selected_topic_id = service.suggest_topic(
                        title=str(item.get("title", source_name)).strip(),
                        preview_text=preview_text[:3000],
                    )
                    if selected_topic_id:
                        updated = service.update_item(
                            str(item.get("id", "")).strip(),
                            topic_id=selected_topic_id,
                        )
                        if updated is not None:
                            item = updated
                service.enqueue_ingest(str(item.get("id", "")).strip())
                rows.append(item)
            finally:
                temp_path.unlink(missing_ok=True)

        status = 201 if rows else 400
        payload: dict[str, Any] = {"items": rows, "errors": errors, "counts": service.counts()}
        if errors and not rows:
            payload["error"] = "\n".join(errors)
        return payload, status

    @bp.get("/api/library/<item_id>")
    def library_get(item_id: str) -> tuple[dict[str, Any], int]:
        profile = ctx.require_profile()
        service = ctx.library_service_for(profile)
        row = service.get_item(item_id)
        if row is None:
            return {"error": "Library item not found."}, 404
        return {"item": row}, 200

    @bp.patch("/api/library/<item_id>")
    def library_update(item_id: str) -> tuple[dict[str, Any], int]:
        profile = ctx.require_profile()
        service = ctx.library_service_for(profile)
        payload = request.get_json(silent=True) or {}
        row = service.update_item(
            item_id,
            title=payload.get("title"),
            source_kind=payload.get("source_kind"),
            topic_id=payload.get("topic_id"),
            project_slug=payload.get("project_slug"),
        )
        if row is None:
            return {"error": "Library item not found."}, 404
        return {"ok": True, "item": row}, 200

    @bp.delete("/api/library/<item_id>")
    def library_delete(item_id: str) -> tuple[dict[str, Any], int]:
        profile = ctx.require_profile()
        service = ctx.library_service_for(profile)
        if not service.delete_item(item_id):
            return {"error": "Library item not found."}, 404
        return {"ok": True, "deleted": item_id}, 200

    @bp.get("/api/library/<item_id>/markdown")
    def library_markdown(item_id: str) -> tuple[dict[str, Any], int]:
        profile = ctx.require_profile()
        service = ctx.library_service_for(profile)
        payload = service.read_markdown(item_id)
        if payload is None:
            return {"error": "Markdown not available for this Library item."}, 404
        return payload, 200

    @bp.get("/api/library/<item_id>/source")
    def library_source(item_id: str):
        profile = ctx.require_profile()
        service = ctx.library_service_for(profile)
        path = service.source_file(item_id)
        if path is None:
            abort(404)
        return send_from_directory(str(path.parent), path.name, as_attachment=False)

    return bp
