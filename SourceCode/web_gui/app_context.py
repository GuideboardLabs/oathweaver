from __future__ import annotations

import logging
import threading
from pathlib import Path
from threading import Lock
from typing import Any

from flask import abort, session

from shared_tools.conversation_store import ConversationStore
from shared_tools.family_auth import FamilyAuthStore
from shared_tools.library_service import LibraryService
from shared_tools.project_pipeline import ProjectPipelineStore
from shared_tools.web_push import (
    get_user_settings as get_web_push_user_settings,
    send_notification as send_web_push_notification,
)
from orchestrator.main import OathweaverOrchestrator
from web_gui.bootstrap import get_watchtower, get_topic_engine
from web_gui.services import JobManager, ForagingManager
from web_gui.services.building_manager import BuildingManager
from web_gui.utils.login_limiter import LoginRateLimiter

LOGGER = logging.getLogger(__name__)


class AppContext:
    """Shared application state passed to blueprint factories.

    Replaces the closure-captured locals that previously lived inside
    ``create_app()``.  Each blueprint receives a single *ctx* instance
    and calls its methods instead of the old closure helpers.
    """

    def __init__(
        self,
        *,
        root: Path,
        auth_store: FamilyAuthStore,
        auth_enabled: bool,
        owner_profile: dict[str, Any],
        owner_id: str,
        panel_cache: dict[str, dict[str, Any]],
        job_manager: JobManager,
        foraging_manager: ForagingManager,
        building_manager: BuildingManager | None = None,
    ) -> None:
        self.root = root
        self.auth_store = auth_store
        self.auth_enabled = auth_enabled
        self.owner_profile = owner_profile
        self.owner_id = owner_id
        self.panel_cache = panel_cache
        self.job_manager = job_manager
        self.foraging_manager = foraging_manager
        self.building_manager: BuildingManager = building_manager or BuildingManager()
        self.project_catalog_lock = Lock()
        self.login_limiter = LoginRateLimiter()
        self._panel_cache_lock = Lock()

    # ------------------------------------------------------------------
    # Profile helpers
    # ------------------------------------------------------------------

    def public_profile(self, profile: dict[str, Any] | None) -> dict[str, Any] | None:
        if not isinstance(profile, dict):
            return None
        return {
            "id": str(profile.get("id", "")).strip(),
            "username": str(profile.get("username", "")).strip(),
            "display_name": str(profile.get("display_name", "")).strip(),
            "role": str(profile.get("role", "adult")).strip().lower() or "adult",
            "color": str(profile.get("color", "#4285f4")).strip() or "#4285f4",
            "is_owner": bool(profile.get("is_owner", False)),
        }

    def session_profile(self) -> dict[str, Any] | None:
        if not self.auth_enabled:
            return self.public_profile(self.owner_profile)
        if not bool(session.get("authenticated", False)):
            return None
        user_id = str(session.get("user_id", "")).strip()
        if not user_id:
            return None
        profile = self.auth_store.get_profile_by_id(user_id)
        if profile is None:
            session.clear()
            return None
        return self.public_profile(profile)

    def require_profile(self) -> dict[str, Any]:
        profile = self.session_profile()
        if profile is None:
            abort(401, description="Authentication required")
        return profile

    def is_legacy_owner(self, profile: dict[str, Any]) -> bool:
        return bool(profile.get("is_owner", False)) and str(profile.get("id", "")).strip() == self.owner_id

    # ------------------------------------------------------------------
    # Path helpers
    # ------------------------------------------------------------------

    def user_workspace_root(self, profile: dict[str, Any]) -> Path:
        uid = str(profile.get("id", "")).strip()
        root = self.root / "Runtime" / "users" / uid / "workspace"
        root.mkdir(parents=True, exist_ok=True)
        return root

    def repo_root_for_profile(self, profile: dict[str, Any]) -> Path:
        if self.is_legacy_owner(profile):
            return self.root
        return self.user_workspace_root(profile)

    # ------------------------------------------------------------------
    # Factory helpers
    # ------------------------------------------------------------------

    def conversation_store_for(self, profile: dict[str, Any]) -> ConversationStore:
        if self.is_legacy_owner(profile):
            return ConversationStore(self.root)
        uid = str(profile.get("id", "")).strip()
        return ConversationStore(self.root, user_id=uid)

    def new_orch(self, profile: dict[str, Any]) -> OathweaverOrchestrator:
        return OathweaverOrchestrator(self.repo_root_for_profile(profile))

    def pipeline_for(self, profile: dict[str, Any]) -> ProjectPipelineStore:
        return ProjectPipelineStore(self.repo_root_for_profile(profile))

    def library_service_for(self, profile: dict[str, Any]) -> LibraryService:
        return LibraryService(self.repo_root_for_profile(profile))

    # ------------------------------------------------------------------
    # Cache
    # ------------------------------------------------------------------

    def cache_clear(self, cache_scope: str | None = None) -> None:
        if not cache_scope:
            self.panel_cache.clear()
            return
        prefix = f"{cache_scope}:"
        for key in list(self.panel_cache.keys()):
            if key.startswith(prefix):
                self.panel_cache.pop(key, None)

    def cache_get(self, cache_scope: str, key: str, ttl_sec: float, build_fn: Any) -> Any:
        import time
        scoped_key = f"{cache_scope}:{key}"
        now = time.monotonic()
        row = self.panel_cache.get(scoped_key)
        if isinstance(row, dict):
            ts = float(row.get("ts", 0.0))
            if now - ts <= ttl_sec:
                return row.get("value")
        value = build_fn()
        self.panel_cache[scoped_key] = {"ts": now, "value": value}
        return value

    # ------------------------------------------------------------------
    # Notification helpers
    # ------------------------------------------------------------------

    def display_name(self, profile: dict[str, Any] | None) -> str:
        if not isinstance(profile, dict):
            return "Oathweaver"
        return str(profile.get("display_name") or profile.get("username") or "Oathweaver").strip() or "Oathweaver"

    def dispatch_web_push(self, user_id: str, payload: dict[str, Any], *, event_key: str = "", test_send: bool = False) -> None:
        uid = str(user_id or "").strip()
        if not uid:
            return

        root = self.root

        def _run() -> None:
            try:
                send_web_push_notification(root, uid, payload, event_key=event_key, test_send=test_send)
            except Exception:
                LOGGER.exception("Web push delivery failed for user %s.", uid)

        threading.Thread(target=_run, daemon=True, name=f"oathweaver-web-push-{uid[:8]}").start()

    def web_push_settings_payload(self, profile: dict[str, Any]) -> dict[str, Any]:
        user_id = str(profile.get("id", "")).strip()
        settings = get_web_push_user_settings(self.root, user_id)
        return {"ok": True, **settings}

    def owner_push_ready(self) -> bool:
        settings = get_web_push_user_settings(self.root, self.owner_id)
        return bool(settings.get("server_supported", False)) and bool(settings.get("has_subscription", False))

    # ------------------------------------------------------------------
    # Background service accessors
    # ------------------------------------------------------------------

    def get_watchtower(self):
        return get_watchtower(self.root)

    def get_topic_engine(self):
        return get_topic_engine(self.root)

    # ------------------------------------------------------------------
    # File root helpers
    # ------------------------------------------------------------------

    def file_roots_for(self, profile: dict[str, Any]) -> tuple[list[Path], list[Path]]:
        if self.is_legacy_owner(profile):
            return [self.root], [self.root / "Runtime" / "users"]
        uid = str(profile.get("id", "")).strip()
        return [self.root / "Runtime" / "users" / uid], []

    # ------------------------------------------------------------------
    # Project catalog helpers
    # ------------------------------------------------------------------

    def _project_catalog_path(self, repo_root: Path) -> Path:
        path = repo_root / "Runtime" / "project_catalog.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        return path

    def load_project_catalog(self, repo_root: Path) -> dict[str, dict[str, Any]]:
        import json
        from web_gui.utils.file_utils import normalize_project_slug as _normalize_project_slug
        path = self._project_catalog_path(repo_root)
        with self.project_catalog_lock:
            if not path.exists():
                return {}
            try:
                payload = json.loads(path.read_text(encoding="utf-8"))
            except (json.JSONDecodeError, OSError):
                return {}
            if not isinstance(payload, dict):
                return {}
            rows = payload.get("projects", {})
            if not isinstance(rows, dict):
                return {}
            out: dict[str, dict[str, Any]] = {}
            for key, value in rows.items():
                slug = _normalize_project_slug(key)
                row = value if isinstance(value, dict) else {}
                out[slug] = {
                    "project": slug,
                    "description": str(row.get("description", "")).strip(),
                    "updated_at": str(row.get("updated_at", "")).strip(),
                }
            return out

    def save_project_catalog(self, repo_root: Path, rows: dict[str, dict[str, Any]]) -> None:
        import json
        path = self._project_catalog_path(repo_root)
        payload = {
            "projects": {
                str(key): {
                    "description": str((value or {}).get("description", "")).strip(),
                    "updated_at": str((value or {}).get("updated_at", "")).strip(),
                }
                for key, value in rows.items()
                if str(key).strip()
            }
        }
        with self.project_catalog_lock:
            tmp = path.with_suffix(".json.tmp")
            tmp.write_text(json.dumps(payload, indent=2, ensure_ascii=True), encoding="utf-8")
            tmp.replace(path)

    # ------------------------------------------------------------------
    # Attachment helpers
    # ------------------------------------------------------------------

    def attachment_dir_for(self, profile: dict[str, Any], conversation_id: str) -> Path:
        import re
        safe_cid = re.sub(r"[^A-Za-z0-9_-]+", "", str(conversation_id or "").strip()) or "unknown"
        path = (self.repo_root_for_profile(profile) / "Runtime" / "attachments" / "conversations" / safe_cid)
        path.mkdir(parents=True, exist_ok=True)
        return path

    def save_uploaded_images(self, profile: dict[str, Any], conversation_id: str) -> tuple[list[dict[str, Any]], list[str]]:
        import mimetypes
        import uuid
        from datetime import datetime, timezone
        from flask import request as _request
        from web_gui.chat_helpers import (
            ATTACHMENT_MAX_IMAGES, ATTACHMENT_MAX_IMAGE_BYTES, ATTACHMENT_MAX_DOC_BYTES,
            ALLOWED_IMAGE_MIME, ALLOWED_IMAGE_EXT, ALLOWED_DOC_MIME, ALLOWED_DOC_EXT,
        )
        from web_gui.utils.file_utils import safe_upload_name as _safe_upload_name
        from web_gui.utils.file_utils import guess_mime_from_ext as _guess_mime_from_ext

        uploaded = _request.files.getlist("images")
        if not uploaded:
            return [], []

        errors: list[str] = []
        attachments: list[dict[str, Any]] = []
        attach_dir = self.attachment_dir_for(profile, conversation_id)

        if len(uploaded) > ATTACHMENT_MAX_IMAGES:
            errors.append(f"Only {ATTACHMENT_MAX_IMAGES} files are allowed per message.")
        allowed_uploads = uploaded[:ATTACHMENT_MAX_IMAGES]

        for file_obj in allowed_uploads:
            original_name = _safe_upload_name(getattr(file_obj, "filename", "") or "file")
            mime = str(getattr(file_obj, "mimetype", "") or "").split(";")[0].strip().lower()
            ext = Path(original_name).suffix.lower()
            if ext == ".jpe":
                ext = ".jpg"

            is_image = ext in ALLOWED_IMAGE_EXT or mime in ALLOWED_IMAGE_MIME
            is_doc = ext in ALLOWED_DOC_EXT or mime in ALLOWED_DOC_MIME

            if is_image:
                if ext not in ALLOWED_IMAGE_EXT:
                    guessed_ext = mimetypes.guess_extension(mime or "") or ""
                    guessed_ext = ".jpg" if guessed_ext == ".jpe" else guessed_ext.lower()
                    if guessed_ext in ALLOWED_IMAGE_EXT:
                        ext = guessed_ext
                if ext not in ALLOWED_IMAGE_EXT:
                    errors.append(f"Unsupported image type: {original_name}")
                    continue
                if mime and mime not in ALLOWED_IMAGE_MIME and not mime.startswith("image/"):
                    errors.append(f"Unsupported image MIME type: {mime}")
                    continue
                blob = file_obj.read(ATTACHMENT_MAX_IMAGE_BYTES + 1)
                if len(blob) > ATTACHMENT_MAX_IMAGE_BYTES:
                    errors.append(f"Image too large: {original_name} (max {ATTACHMENT_MAX_IMAGE_BYTES // (1024 * 1024)}MB)")
                    continue
                if not blob:
                    continue
                attach_id = uuid.uuid4().hex[:10]
                ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
                stored_name = f"{ts}_{attach_id}{ext}"
                (attach_dir / stored_name).write_bytes(blob)
                final_mime = mime if mime in ALLOWED_IMAGE_MIME else _guess_mime_from_ext(ext)
                attachments.append({
                    "id": attach_id, "type": "image", "name": original_name,
                    "filename": stored_name, "mime": final_mime, "size": len(blob),
                    "url": f"/api/conversations/{conversation_id}/attachments/{stored_name}",
                })
            elif is_doc:
                blob = file_obj.read(ATTACHMENT_MAX_DOC_BYTES + 1)
                if len(blob) > ATTACHMENT_MAX_DOC_BYTES:
                    errors.append(f"Document too large: {original_name} (max {ATTACHMENT_MAX_DOC_BYTES // (1024 * 1024)}MB)")
                    continue
                if not blob:
                    continue
                attach_id = uuid.uuid4().hex[:10]
                ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
                stored_name = f"{ts}_{attach_id}{ext}"
                dest = attach_dir / stored_name
                dest.write_bytes(blob)
                extracted_text = ""
                extraction_warning = ""
                try:
                    from shared_tools.document_ingestion import extract_text as _extract_doc_text
                    from shared_tools.optional_features import feature_warning as _feature_warning
                    extracted_text = _extract_doc_text(dest, mime)
                    if not extracted_text and ext in {".pdf", ".doc", ".docx"}:
                        extraction_warning = _feature_warning("document_extraction")
                except Exception:
                    LOGGER.exception("Document extraction failed for %s.", original_name)
                    extraction_warning = "document extraction failed unexpectedly"
                attachments.append({
                    "id": attach_id, "type": "document", "name": original_name,
                    "filename": stored_name, "mime": mime or _guess_mime_from_ext(ext),
                    "size": len(blob),
                    "url": f"/api/conversations/{conversation_id}/attachments/{stored_name}",
                    "extracted_text": extracted_text[:32_000],
                    "extraction_warning": extraction_warning,
                })
            else:
                errors.append(f"Unsupported file type: {original_name}")

        return attachments, errors

    def describe_image_attachments(
        self,
        profile: dict[str, Any],
        conversation_id: str,
        orch: Any,
        attachments: list[dict[str, Any]],
        user_text: str,
    ) -> tuple[str, list[str]]:
        import base64
        from web_gui.chat_helpers import vision_model_candidates, ATTACHMENT_MAX_IMAGES
        if not attachments:
            return "", []
        candidates = vision_model_candidates(orch)
        if not candidates:
            names = ", ".join([str(x.get("name", "")) for x in attachments][:6])
            return (
                "Image attachment(s) received but no local vision model is configured. "
                f"Files: {names}"
            ), []
        attach_dir = self.attachment_dir_for(profile, conversation_id)
        summaries: list[str] = []
        failures: list[str] = []
        prompt_focus = user_text.strip() or "Describe important details, text, and context in this image."
        system_prompt = (
            "You are a visual analyst for Oathweaver. "
            "Describe what is visible, extract any readable text, and infer relevant context. "
            "Be concrete and concise."
        )
        for idx, row in enumerate(attachments[:ATTACHMENT_MAX_IMAGES], start=1):
            stored_name = str(row.get("filename", "")).strip()
            if not stored_name:
                continue
            image_path = attach_dir / stored_name
            if not image_path.exists():
                failures.append(f"{stored_name}: missing file")
                continue
            image_b64 = base64.b64encode(image_path.read_bytes()).decode("ascii")
            analyzed = False
            last_exc = ""
            for model in candidates:
                try:
                    response = orch.ollama.chat(
                        model=model,
                        system_prompt=system_prompt,
                        user_prompt=(
                            f"User request/context: {prompt_focus}\n\n"
                            "Analyze the attached image and return a practical summary."
                        ),
                        user_images=[image_b64],
                        temperature=0.2,
                        num_ctx=8192,
                        timeout=180,
                    )
                    clean = " ".join(str(response).split())
                    summaries.append(f"[Image {idx} | {model}] {clean}")
                    analyzed = True
                    break
                except Exception as exc:
                    last_exc = str(exc)
                    continue
            if not analyzed:
                failures.append(f"{stored_name}: {last_exc or 'all local vision models failed'}")
        if not summaries:
            return "", failures
        header = f"Image context ({len(summaries)} analyzed):"
        body = "\n".join([f"- {line}" for line in summaries])
        return f"{header}\n{body}", failures

    def conversation_notification_payload(
        self,
        *,
        profile: dict[str, Any],
        conversation: dict[str, Any],
        message: dict[str, Any],
    ) -> tuple[dict[str, Any], str]:
        conversation_id = str(conversation.get("id", "")).strip()
        title_text = str(conversation.get("title", "")).strip() or "Conversation"
        raw_content = str(message.get("content", "")).strip() or "Oathweaver posted a new reply."
        compact = " ".join(raw_content.split())
        preview = compact[:157] + "..." if len(compact) > 160 else compact
        is_foraging = bool(message.get("foraging", False))
        is_building = bool(message.get("building", False))
        if is_foraging:
            title = f"Foraging finished in {title_text}"
        elif is_building:
            title = f"Build finished in {title_text}"
        else:
            title = f"New message in {title_text}"
        body = preview or f"{self.display_name(profile)} has a new Oathweaver reply."
        cid = str(conversation_id or "").strip()
        url = f"/#{cid}" if cid else "/"
        payload = {
            "title": title, "body": body, "url": url,
            "conversation_id": conversation_id,
            "tag": f"conversation:{conversation_id}",
            "icon": "/static/branding/logo.png",
            "badge": "/static/branding/logo.png",
            "renotify": is_foraging or is_building,
        }
        event_key = f"conversation:{str(profile.get('id', '')).strip()}:{conversation_id}:{str(message.get('id', '')).strip()}"
        return payload, event_key

    # ------------------------------------------------------------------
    # Forage card helpers
    # ------------------------------------------------------------------

    def forage_card_repo(self) -> Any:
        from infra.persistence.repositories import ForageCardRepository
        return ForageCardRepository(self.root)

    def forage_cards_pinned_count(self) -> int:
        try:
            return self.forage_card_repo().pinned_count()
        except Exception:
            return 0

    # ------------------------------------------------------------------
    # Oathweaver settings helpers
    # ------------------------------------------------------------------

    def _oathweaver_settings_path(self) -> Path:
        p = self.root / "Runtime" / "config" / "oathweaver_settings.json"
        p.parent.mkdir(parents=True, exist_ok=True)
        return p

    def load_oathweaver_settings(self) -> dict[str, Any]:
        import json
        p = self._oathweaver_settings_path()
        if not p.exists():
            return {}
        try:
            raw = json.loads(p.read_text(encoding="utf-8"))
            return raw if isinstance(raw, dict) else {}
        except Exception:
            return {}

    def save_oathweaver_settings(self, data: dict[str, Any]) -> None:
        import json
        p = self._oathweaver_settings_path()
        tmp = p.with_suffix(".json.tmp")
        tmp.write_text(json.dumps(data, indent=2, ensure_ascii=True), encoding="utf-8")
        tmp.replace(p)

    # ------------------------------------------------------------------
    # Project catalog helpers (continued)
    # ------------------------------------------------------------------

    def set_project_catalog_entry(self, repo_root: Path, project: str, description: str) -> dict[str, Any]:
        import datetime
        from web_gui.utils.file_utils import normalize_project_slug as _normalize_project_slug
        slug = _normalize_project_slug(project)
        rows = self.load_project_catalog(repo_root)
        rows[slug] = {
            "project": slug,
            "description": str(description or "").strip(),
            "updated_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        }
        self.save_project_catalog(repo_root, rows)
        return rows[slug]
