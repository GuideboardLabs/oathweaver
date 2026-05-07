from __future__ import annotations

import json
from pathlib import Path
from typing import TYPE_CHECKING, Any

from flask import Blueprint, abort, request, send_from_directory

from web_gui.chat_helpers import DEFAULT_PROJECT, GENERAL_PROJECT
from web_gui.utils.file_utils import (
    guess_mime_from_ext as _guess_mime_from_ext,
    normalize_project_slug as _normalize_project_slug,
    read_text_file_preview as _read_text_file_preview,
    safe_markdown_path as _safe_markdown_path,
    safe_path_in_roots as _safe_path_in_roots,
    safe_upload_name as _safe_upload_name,
)

if TYPE_CHECKING:
    from web_gui.app_context import AppContext


def register_conversation_routes(bp: Blueprint, ctx: AppContext) -> None:
    def _normalize_lora_selection(raw: Any) -> list[str]:
        values = raw if isinstance(raw, list) else []
        seen: set[str] = set()
        out: list[str] = []
        for item in values:
            text = str(item or "").strip()
            if not text or text in seen:
                continue
            seen.add(text)
            out.append(text[:220])
            if len(out) >= 32:
                break
        return out

    @bp.route("/api/markdown", methods=["GET"])
    def read_markdown_file() -> tuple[dict, int]:
        profile = ctx.require_profile()
        raw_path = str(request.args.get("path", "")).strip()
        if not raw_path:
            return {"error": "Markdown path is required"}, 400
        allowed_roots, denied_roots = ctx.file_roots_for(profile)
        safe_path = _safe_markdown_path(raw_path, allowed_roots=allowed_roots, denied_roots=denied_roots)
        if safe_path is None:
            return {"error": "Invalid markdown path"}, 400
        try:
            content = safe_path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            content = safe_path.read_text(encoding="utf-8-sig")
        return {"path": str(safe_path), "name": safe_path.name, "content": content}, 200

    @bp.route("/api/files/read", methods=["GET"])
    def read_project_file() -> tuple[dict, int]:
        profile = ctx.require_profile()
        raw_path = str(request.args.get("path", "")).strip()
        if not raw_path:
            return {"error": "File path is required"}, 400
        allowed_roots, denied_roots = ctx.file_roots_for(profile)
        safe_path = _safe_path_in_roots(raw_path, allowed_roots=allowed_roots, denied_roots=denied_roots, must_exist=True)
        if safe_path is None or not safe_path.is_file():
            return {"error": "Invalid file path"}, 400
        ext = safe_path.suffix.lower()
        mime = _guess_mime_from_ext(ext)
        content, truncated, binary = _read_text_file_preview(safe_path, max_bytes=250_000)
        if binary:
            return {
                "path": str(safe_path),
                "name": safe_path.name,
                "ext": ext,
                "mime": mime,
                "size": int(safe_path.stat().st_size),
                "render": "binary",
                "truncated": False,
                "content": "",
            }, 200
        render = "text"
        if ext == ".md":
            render = "markdown"
        elif ext == ".json":
            render = "json"
            try:
                content = json.dumps(json.loads(content), indent=2, ensure_ascii=False)
            except (json.JSONDecodeError, ValueError):
                pass
        try:
            file_size = int(safe_path.stat().st_size)
        except OSError:
            file_size = len(content.encode("utf-8", errors="ignore"))
        return {
            "path": str(safe_path),
            "name": safe_path.name,
            "ext": ext,
            "mime": mime,
            "size": file_size,
            "render": render,
            "truncated": bool(truncated),
            "content": content,
        }, 200

    @bp.route("/api/conversations", methods=["GET"])
    def list_conversations() -> tuple[dict, int]:
        profile = ctx.require_profile()
        store = ctx.conversation_store_for(profile)
        return {"conversations": store.list()}, 200

    @bp.route("/api/conversations", methods=["POST"])
    def create_conversation() -> tuple[dict, int]:
        profile = ctx.require_profile()
        store = ctx.conversation_store_for(profile)
        payload = request.get_json(silent=True) or {}
        title = str(payload.get("title", "New Thread"))
        kind = str(payload.get("kind", "")).strip().lower()
        topic_id = str(payload.get("topic_id", "")).strip()
        project = _normalize_project_slug(payload.get("project")) if "project" in payload else GENERAL_PROJECT
        if kind == "general":
            project = GENERAL_PROJECT
            topic_id = "general"
        if not topic_id and project == GENERAL_PROJECT:
            topic_id = "general"
        if project == GENERAL_PROJECT and title.strip() in {"New Thread", "New Chat"} and kind == "general":
            title = "General Thread"
        path = ""
        if topic_id and topic_id != "general" and project != GENERAL_PROJECT:
            path = store._generate_path(project, title)
        convo = store.create(title=title, project=project, topic_id=topic_id or "general", path=path)
        ctx.cache_clear(str(profile.get("id", "")))
        return {"conversation": convo}, 201

    @bp.route("/api/conversations/<conversation_id>", methods=["DELETE"])
    def delete_conversation(conversation_id: str) -> tuple[dict, int]:
        profile = ctx.require_profile()
        store = ctx.conversation_store_for(profile)
        deleted = store.delete(conversation_id)
        if not deleted:
            abort(404, description="Conversation not found")
        ctx.cache_clear(str(profile.get("id", "")))
        return {"ok": True, "conversation_id": conversation_id}, 200

    @bp.route("/api/conversations/<conversation_id>", methods=["GET"])
    def get_conversation(conversation_id: str) -> tuple[dict, int]:
        profile = ctx.require_profile()
        store = ctx.conversation_store_for(profile)
        convo = store.get(conversation_id)
        if convo is None:
            abort(404, description="Conversation not found")
        if not str(convo.get("project", "")).strip():
            convo = store.set_project(conversation_id, DEFAULT_PROJECT) or convo
        if not str(convo.get("topic_id", "")).strip():
            convo = store.set_topic(
                conversation_id,
                "general" if str(convo.get("project", DEFAULT_PROJECT)).strip() == DEFAULT_PROJECT else "",
            ) or convo
        return {"conversation": convo}, 200

    @bp.route("/api/conversations/<conversation_id>", methods=["PATCH"])
    def rename_conversation(conversation_id: str) -> tuple[dict, int]:
        profile = ctx.require_profile()
        store = ctx.conversation_store_for(profile)
        payload = request.get_json(silent=True) or {}
        title = str(payload.get("title", "")).strip()
        project_raw = payload.get("project")
        topic_id_raw = payload.get("topic_id")
        image_style_raw = payload.get("image_style") if "image_style" in payload else None
        selected_loras_raw = payload.get("selected_loras") if "selected_loras" in payload else None
        if (
            not title
            and project_raw is None
            and topic_id_raw is None
            and image_style_raw is None
            and selected_loras_raw is None
        ):
            return {"error": "Either title, project, topic_id, image_style, or selected_loras is required"}, 400
        updated = store.get(conversation_id)
        if updated is None:
            abort(404, description="Conversation not found")
        if title:
            updated = store.rename(conversation_id, title=title)
            if updated is None:
                abort(404, description="Conversation not found")
        if project_raw is not None:
            project = _normalize_project_slug(project_raw)
            updated = store.set_project(conversation_id, project=project)
            if updated is None:
                abort(404, description="Conversation not found")
        if topic_id_raw is not None:
            topic_id = str(topic_id_raw or "").strip()
            if not topic_id and str((updated or {}).get("project", "")).strip() == DEFAULT_PROJECT:
                topic_id = "general"
            updated = store.set_topic(conversation_id, topic_id)
            if updated is None:
                abort(404, description="Conversation not found")
        if image_style_raw is not None or selected_loras_raw is not None:
            selected_loras: list[str] | None = None
            if selected_loras_raw is not None:
                if isinstance(selected_loras_raw, list):
                    selected_loras = _normalize_lora_selection(selected_loras_raw)
                elif isinstance(selected_loras_raw, str):
                    parsed: list[str] = []
                    raw_text = selected_loras_raw.strip()
                    if raw_text.startswith("["):
                        try:
                            maybe = json.loads(raw_text)
                            if isinstance(maybe, list):
                                parsed = [str(x) for x in maybe]
                        except json.JSONDecodeError:
                            parsed = []
                    else:
                        parsed = [part.strip() for part in raw_text.split(",") if part.strip()]
                    selected_loras = _normalize_lora_selection(parsed)
                else:
                    selected_loras = []
            updated = store.set_image_preferences(
                conversation_id,
                image_style=(str(image_style_raw) if image_style_raw is not None else None),
                selected_loras=selected_loras,
            )
            if updated is None:
                abort(404, description="Conversation not found")
        if updated is None:
            abort(500, description="Failed to update conversation")
        ctx.cache_clear(str(profile.get("id", "")))
        return {"conversation": updated}, 200

    @bp.route("/api/conversations/<conversation_id>/read", methods=["POST"])
    def mark_conversation_read(conversation_id: str) -> tuple[dict, int]:
        profile = ctx.require_profile()
        store = ctx.conversation_store_for(profile)
        convo = store.mark_read(conversation_id)
        if convo is None:
            abort(404, description="Conversation not found")
        return {"ok": True, "conversation": convo}, 200

    @bp.route("/api/conversations/<conversation_id>/attachments/<filename>", methods=["GET"])
    def get_conversation_attachment(conversation_id: str, filename: str) -> Any:
        profile = ctx.require_profile()
        store = ctx.conversation_store_for(profile)
        convo = store.get(conversation_id)
        if convo is None:
            abort(404, description="Conversation not found")
        raw_name = str(filename or "").strip()
        if not raw_name or "/" in raw_name or "\\" in raw_name:
            abort(404, description="Attachment not found")
        safe_name = _safe_upload_name(raw_name)
        if safe_name != raw_name:
            abort(404, description="Attachment not found")
        attach_dir = ctx.attachment_dir_for(profile, conversation_id)
        path = attach_dir / safe_name
        if not path.exists() or not path.is_file():
            abort(404, description="Attachment not found")
        return send_from_directory(str(attach_dir), safe_name, as_attachment=False, mimetype=_guess_mime_from_ext(path.suffix))
