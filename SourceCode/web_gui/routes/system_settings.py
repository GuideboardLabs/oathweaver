from __future__ import annotations

import json
import re
import time
from pathlib import Path
from typing import TYPE_CHECKING, Any

from flask import Blueprint, request

from web_gui.routes.system_support import _STATIC_DIR

if TYPE_CHECKING:
    from web_gui.app_context import AppContext


def register_settings_routes(bp: Blueprint, ctx: AppContext) -> None:
    @bp.route("/api/settings/foraging", methods=["POST"])
    def set_foraging_state() -> tuple[dict, int]:
        profile = ctx.require_profile()
        payload = request.get_json(silent=True) or {}
        raw_paused = payload.get("paused", None)
        if raw_paused is None:
            paused = not ctx.foraging_manager.is_paused()
        else:
            paused = bool(raw_paused)
        value = ctx.foraging_manager.set_paused(paused)
        ctx.cache_clear(str(profile.get("id", "")))
        snapshot = ctx.foraging_manager.snapshot(profile_id=str(profile.get("id", "")))
        return {"ok": True, "paused": value, **snapshot}, 200

    @bp.route("/api/settings/building", methods=["POST"])
    def set_building_state() -> tuple[dict, int]:
        profile = ctx.require_profile()
        payload = request.get_json(silent=True) or {}
        raw_paused = payload.get("paused", None)
        if raw_paused is None:
            paused = not ctx.building_manager.is_paused()
        else:
            paused = bool(raw_paused)
        value = ctx.building_manager.set_paused(paused)
        ctx.cache_clear(str(profile.get("id", "")))
        snapshot = ctx.building_manager.snapshot(profile_id=str(profile.get("id", "")))
        return {"ok": True, "paused": value, **snapshot}, 200

    @bp.route("/api/settings/web-mode", methods=["POST"])
    def set_web_mode() -> tuple[dict, int]:
        profile = ctx.require_profile()
        payload = request.get_json(silent=True) or {}
        mode = str(payload.get("mode", "")).strip().lower()
        if mode not in {"off", "ask", "auto"}:
            return {"ok": False, "error": "Invalid mode. Use off, ask, or auto."}, 400
        orch = ctx.new_orch(profile)
        try:
            value = orch.web_engine.set_mode(mode)
        except ValueError as exc:
            return {"ok": False, "error": str(exc)}, 400
        ctx.cache_clear(str(profile.get("id", "")))
        return {"ok": True, "mode": value}, 200

    @bp.route("/api/settings/external-tools-mode", methods=["POST"])
    def set_external_tools_mode() -> tuple[dict, int]:
        profile = ctx.require_profile()
        payload = request.get_json(silent=True) or {}
        mode = str(payload.get("mode", "")).strip().lower()
        if mode not in {"off", "ask", "auto"}:
            return {"ok": False, "error": "Invalid mode. Use off, ask, or auto."}, 400
        orch = ctx.new_orch(profile)
        result_text = orch.set_external_tools_mode(mode)
        if result_text.lower().startswith("invalid"):
            return {"ok": False, "error": result_text}, 400
        ctx.cache_clear(str(profile.get("id", "")))
        return {"ok": True, "mode": orch.external_tools_settings.get_mode()}, 200

    @bp.route("/api/settings/web-push", methods=["GET"])
    def get_web_push_settings() -> tuple[dict, int]:
        profile = ctx.require_profile()
        return ctx.web_push_settings_payload(profile), 200

    @bp.route("/api/settings/web-push/subscribe", methods=["POST"])
    def subscribe_web_push() -> tuple[dict, int]:
        from shared_tools.web_push import subscribe_user as _subscribe

        profile = ctx.require_profile()
        payload = request.get_json(silent=True) or {}
        subscription = payload.get("subscription", {})
        installed = bool(payload.get("installed", False))
        user_agent = str(request.headers.get("User-Agent", "")).strip()
        try:
            _subscribe(
                ctx.root,
                str(profile.get("id", "")).strip(),
                subscription,
                user_agent=user_agent,
                installed=installed,
            )
        except ValueError as exc:
            return {"ok": False, "error": str(exc)}, 400
        return ctx.web_push_settings_payload(profile), 200

    @bp.route("/api/settings/web-push/unsubscribe", methods=["POST"])
    def unsubscribe_web_push() -> tuple[dict, int]:
        from shared_tools.web_push import unsubscribe_user as _unsubscribe

        profile = ctx.require_profile()
        payload = request.get_json(silent=True) or {}
        endpoint = str(payload.get("endpoint", "")).strip()
        _unsubscribe(ctx.root, str(profile.get("id", "")).strip(), endpoint)
        return ctx.web_push_settings_payload(profile), 200

    @bp.route("/api/settings/web-push/test", methods=["POST"])
    def test_web_push() -> tuple[dict, int]:
        profile = ctx.require_profile()
        settings = ctx.web_push_settings_payload(profile)
        if not bool(settings.get("server_supported", False)):
            return {"ok": False, "error": str(settings.get("last_error", "")).strip() or "Web Push is not configured on the server."}, 400
        if not bool(settings.get("has_subscription", False)):
            return {"ok": False, "error": "No device is subscribed for this account yet."}, 400
        push_payload = {
            "title": "Oathweaver push test",
            "body": f"Push notifications are working for {ctx.display_name(profile)}.",
            "url": "/",
            "tag": f"push-test:{str(profile.get('id', '')).strip()}",
            "icon": "/static/branding/logo.png",
            "badge": "/static/branding/logo.png",
        }
        ctx.dispatch_web_push(
            str(profile.get("id", "")).strip(),
            push_payload,
            event_key=f"push-test:{str(profile.get('id', '')).strip()}:{int(time.time())}",
            test_send=True,
        )
        return {"ok": True}, 200

    @bp.route("/api/settings/fonts", methods=["GET"])
    def settings_fonts() -> tuple[dict, int]:
        fonts_dir = _STATIC_DIR / "fonts"
        config_path = fonts_dir / "font-config.json"
        default_fallback = '"Segoe UI", "Trebuchet MS", sans-serif'
        format_map = {".ttf": "truetype", ".otf": "opentype", ".woff": "woff", ".woff2": "woff2"}

        def _slugify(raw: str) -> str:
            key = re.sub(r"[^a-z0-9]+", "_", str(raw or "").strip().lower()).strip("_")
            return key or "font"

        def _family_from_stem(stem: str) -> str:
            text = re.sub(r"[_\\-]+", " ", str(stem or "").strip())
            text = re.sub(r"\s+", " ", text).strip()
            if not text:
                return "Custom Font"
            return " ".join(part.capitalize() if part.islower() else part for part in text.split(" "))

        def _infer_weight_style(name_hint: str) -> tuple[str, str]:
            raw = re.sub(r"([a-z0-9])([A-Z])", r"\1 \2", str(name_hint or "").strip())
            key = re.sub(r"\s+", " ", raw.lower().replace("_", " ").replace("-", " "))
            style = "italic" if (" italic" in f" {key} " or " oblique" in f" {key} ") else "normal"
            weight = "400"
            checks = [
                ("hairline", "100"), ("thin", "100"), ("extra light", "200"), ("extralight", "200"),
                ("ultra light", "200"), ("ultralight", "200"), ("light", "300"), ("book", "400"),
                ("regular", "400"), ("normal", "400"), ("medium", "500"), ("semi bold", "600"),
                ("semibold", "600"), ("demi bold", "600"), ("demibold", "600"), ("extra bold", "800"),
                ("extrabold", "800"), ("ultra bold", "800"), ("ultrabold", "800"), ("bold", "700"),
                ("black", "900"), ("heavy", "900"),
            ]
            padded = f" {key} "
            for token, value in checks:
                if f" {token} " in padded:
                    weight = value
            return weight, style

        def _normalize_row(row: Any) -> dict[str, str] | None:
            if not isinstance(row, dict):
                return None
            font_id = str(row.get("id", "")).strip().lower()
            family = str(row.get("family", "")).strip()
            if not font_id or not family or re.search(r"[{};]", family):
                return None
            file_text = str(row.get("file", "")).strip().replace("\\", "/")
            while file_text.startswith("/"):
                file_text = file_text[1:]
            if ".." in file_text:
                file_text = ""
            ext = Path(file_text).suffix.lower() if file_text else ""
            font_format = str(row.get("format", "")).strip().lower() or format_map.get(ext, "truetype")
            hint = f"{family} {Path(file_text).stem if file_text else ''}"
            inferred_weight, inferred_style = _infer_weight_style(hint)
            return {
                "id": font_id,
                "family": family,
                "file": file_text,
                "format": font_format,
                "weight": str(row.get("weight", "")).strip() or inferred_weight or "400",
                "style": str(row.get("style", "")).strip().lower() or inferred_style or "normal",
                "fallback": str(row.get("fallback", "")).strip(),
            }

        payload: dict[str, Any] = {}
        if config_path.exists():
            try:
                payload = json.loads(config_path.read_text(encoding="utf-8"))
                if not isinstance(payload, dict):
                    payload = {}
            except Exception:
                payload = {}

        configured_rows = payload.get("fonts", [])
        fonts: list[dict[str, str]] = []
        used_ids: set[str] = set()
        used_files: set[str] = set()

        for row in configured_rows if isinstance(configured_rows, list) else []:
            normalized = _normalize_row(row)
            if not normalized or normalized["id"] in used_ids:
                continue
            used_ids.add(normalized["id"])
            if normalized["file"]:
                used_files.add(normalized["file"].lower())
            fonts.append(normalized)

        system_presets = [
            ("system_ui", "Segoe UI"),
            ("trebuchet_ms", "Trebuchet MS"),
            ("arial", "Arial"),
            ("verdana", "Verdana"),
            ("tahoma", "Tahoma"),
            ("helvetica_neue", "Helvetica Neue"),
            ("georgia", "Georgia"),
            ("times_new_roman", "Times New Roman"),
            ("courier_new", "Courier New"),
            ("consolas", "Consolas"),
        ]
        existing_families = {str(row.get("family", "")).strip().lower() for row in fonts}
        for font_id, family in system_presets:
            if font_id in used_ids or family.lower() in existing_families:
                continue
            fonts.append({
                "id": font_id,
                "family": family,
                "file": "",
                "format": "truetype",
                "weight": "400",
                "style": "normal",
                "fallback": default_fallback,
            })
            used_ids.add(font_id)
            existing_families.add(family.lower())

        if fonts_dir.exists():
            for path in sorted(fonts_dir.rglob("*")):
                if not path.is_file() or path.name.lower() == "font-config.json":
                    continue
                ext = path.suffix.lower()
                if ext not in format_map:
                    continue
                rel = path.relative_to(fonts_dir).as_posix()
                if rel.lower() in used_files:
                    continue
                base_id = _slugify(path.stem)
                next_id = base_id
                counter = 2
                while next_id in used_ids:
                    next_id = f"{base_id}_{counter}"
                    counter += 1
                inferred_weight, inferred_style = _infer_weight_style(path.stem)
                fonts.append({
                    "id": next_id,
                    "family": _family_from_stem(path.stem),
                    "file": rel,
                    "format": format_map.get(ext, "truetype"),
                    "weight": inferred_weight or "400",
                    "style": inferred_style or "normal",
                    "fallback": default_fallback,
                })
                used_ids.add(next_id)
                used_files.add(rel.lower())

        return {
            "active": str(payload.get("active", "")).strip().lower(),
            "active_family": str(payload.get("active_family", "")).strip(),
            "fallback": str(payload.get("fallback", default_fallback)).strip() or default_fallback,
            "fonts": fonts,
        }, 200

    @bp.route("/api/settings/morning-digest", methods=["GET"])
    def get_digest_settings() -> tuple[dict, int]:
        ctx.require_profile()
        cfg = ctx.load_oathweaver_settings()
        return {
            "ok": True,
            "morning_digest_enabled": bool(cfg.get("morning_digest_enabled", False)),
            "morning_digest_hour": int(cfg.get("morning_digest_hour", 7)),
            "digest_location_lat": cfg.get("digest_location_lat"),
            "digest_location_lon": cfg.get("digest_location_lon"),
            "digest_location_label": cfg.get("digest_location_label", ""),
        }, 200

    @bp.route("/api/settings/morning-digest", methods=["POST"])
    def save_digest_settings() -> tuple[dict, int]:
        ctx.require_profile()
        payload = request.get_json(silent=True) or {}
        cfg = ctx.load_oathweaver_settings()
        if "morning_digest_enabled" in payload:
            cfg["morning_digest_enabled"] = bool(payload["morning_digest_enabled"])
        if "morning_digest_hour" in payload:
            cfg["morning_digest_hour"] = max(0, min(23, int(payload["morning_digest_hour"])))
        if "digest_location_lat" in payload:
            cfg["digest_location_lat"] = payload["digest_location_lat"]
        if "digest_location_lon" in payload:
            cfg["digest_location_lon"] = payload["digest_location_lon"]
        if "digest_location_label" in payload:
            cfg["digest_location_label"] = str(payload["digest_location_label"] or "")
        ctx.save_oathweaver_settings(cfg)
        return {"ok": True}, 200

    @bp.route("/api/forage-cards", methods=["GET"])
    def forage_cards_list() -> tuple[dict, int]:
        from web_gui.utils.request_utils import parse_optional_int

        ctx.require_profile()
        limit = parse_optional_int(request.args.get("limit"), default=50, minimum=1, maximum=200)
        cards = ctx.forage_card_repo().list_cards(limit=limit)
        return {"ok": True, "cards": cards}, 200

    @bp.route("/api/forage-cards/<card_id>/pin", methods=["POST"])
    def forage_card_pin(card_id: str) -> tuple[dict, int]:
        ctx.require_profile()
        repo = ctx.forage_card_repo()
        resolved_id = repo.resolve_card_id(card_id)
        if not resolved_id:
            return {"ok": False, "message": "Card not found."}, 404
        card = repo.get_card(resolved_id)
        if card is None:
            return {"ok": False, "message": "Card not found."}, 404
        if int(card.get("is_pinned", 0)):
            ok = repo.unpin_card(resolved_id)
        else:
            ok = repo.pin_card(resolved_id)
        return {"ok": ok, "card": repo.get_card(resolved_id)}, 200

    @bp.route("/api/forage-cards/<card_id>", methods=["DELETE"])
    def forage_card_delete(card_id: str) -> tuple[dict, int]:
        ctx.require_profile()
        return {"ok": ctx.forage_card_repo().delete_card(card_id)}, 200
