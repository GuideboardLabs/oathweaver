from __future__ import annotations

import json
from pathlib import Path
from typing import TYPE_CHECKING, Any

from flask import Blueprint, request

from shared_tools.optional_features import optional_feature_status

if TYPE_CHECKING:
    from web_gui.app_context import AppContext


def register_owner_routes(bp: Blueprint, ctx: AppContext) -> None:
    @bp.route("/api/owner/email-settings", methods=["GET"])
    def get_email_settings() -> tuple[dict, int]:
        from shared_tools.email_notifier import load_email_config, is_configured

        profile = ctx.require_profile()
        if not bool(profile.get("is_owner", False)):
            return {"ok": False, "error": "Owner only."}, 403
        cfg = load_email_config(ctx.root)
        return {
            "ok": True,
            "settings": {
                "notification_email": cfg.get("notification_email", ""),
                "smtp_user_configured": bool(str(cfg.get("smtp_user", "")).strip()),
                "smtp_configured": is_configured(cfg),
                "dnd_enabled": bool(cfg.get("dnd_enabled", False)),
                "dnd_start": cfg.get("dnd_start", "22:00"),
                "dnd_end": cfg.get("dnd_end", "08:00"),
            },
        }, 200

    @bp.route("/api/owner/email-settings", methods=["POST"])
    def save_email_settings() -> tuple[dict, int]:
        from shared_tools.email_notifier import load_email_config, save_email_config

        profile = ctx.require_profile()
        if not bool(profile.get("is_owner", False)):
            return {"ok": False, "error": "Owner only."}, 403
        payload = request.get_json(silent=True) or {}
        cfg = load_email_config(ctx.root)
        cfg["notification_email"] = str(payload.get("notification_email", cfg.get("notification_email", ""))).strip()
        cfg["smtp_user"] = str(payload.get("smtp_user", cfg.get("smtp_user", ""))).strip()
        pw = str(payload.get("smtp_password", "")).strip()
        if pw:
            cfg["smtp_password"] = pw
        if "dnd_enabled" in payload:
            cfg["dnd_enabled"] = bool(payload["dnd_enabled"])
        if "dnd_start" in payload:
            cfg["dnd_start"] = str(payload["dnd_start"]).strip() or "22:00"
        if "dnd_end" in payload:
            cfg["dnd_end"] = str(payload["dnd_end"]).strip() or "08:00"
        save_email_config(ctx.root, cfg)
        return {"ok": True}, 200

    @bp.route("/api/owner/email-settings/test", methods=["POST"])
    def test_email_settings() -> tuple[dict, int]:
        from shared_tools.email_notifier import load_email_config, is_configured, send_notification_email

        profile = ctx.require_profile()
        if not bool(profile.get("is_owner", False)):
            return {"ok": False, "error": "Owner only."}, 403
        cfg = load_email_config(ctx.root)
        if not is_configured(cfg):
            return {"ok": False, "error": "Email not fully configured."}, 400
        try:
            send_notification_email(cfg, "Oathweaver — test notification", "Email notifications are working.")
            return {"ok": True}, 200
        except Exception as exc:
            return {"ok": False, "error": str(exc)}, 500

    @bp.route("/api/owner/bot-config", methods=["GET"])
    def get_bot_config() -> tuple[dict, int]:
        from bots.bot_config import load_bot_config

        profile = ctx.require_profile()
        if not bool(profile.get("is_owner", False)):
            return {"ok": False, "error": "Owner only."}, 403
        cfg = load_bot_config(ctx.root)
        feature_status = optional_feature_status()
        safe: dict[str, dict[str, Any]] = {}
        for platform, pcfg in cfg.items():
            availability = feature_status.get(f"{platform}_bot", {})
            safe[platform] = {
                "enabled": bool(pcfg.get("enabled", False)),
                "configured": bool(str(pcfg.get("bot_token", "")).strip()),
                "available": bool(availability.get("available", True)),
                "missing": list(availability.get("missing", [])),
                "install_hint": str(availability.get("install_hint", "")).strip(),
            }
        return {"ok": True, "config": safe}, 200

    @bp.route("/api/owner/bot-config", methods=["POST"])
    def save_bot_config() -> tuple[dict, int]:
        from bots.bot_config import save_bot_config as _save

        profile = ctx.require_profile()
        if not bool(profile.get("is_owner", False)):
            return {"ok": False, "error": "Owner only."}, 403
        payload = request.get_json(silent=True) or {}
        _save(ctx.root, payload)
        return {"ok": True}, 200

    @bp.route("/api/owner/bot-users", methods=["GET"])
    def list_bot_users() -> tuple[dict, int]:
        from bots.bot_user_store import BotUserStore

        profile = ctx.require_profile()
        if not bool(profile.get("is_owner", False)):
            return {"ok": False, "error": "Owner only."}, 403
        platform = request.args.get("platform") or None
        mappings = BotUserStore(ctx.root).list_mappings(platform=platform)
        return {"ok": True, "mappings": mappings}, 200

    @bp.route("/api/owner/bot-users", methods=["POST"])
    def create_bot_user() -> tuple[dict, int]:
        from bots.bot_user_store import BotUserStore
        from shared_tools.conversation_store import ConversationStore

        profile = ctx.require_profile()
        if not bool(profile.get("is_owner", False)):
            return {"ok": False, "error": "Owner only."}, 403
        payload = request.get_json(silent=True) or {}
        platform = str(payload.get("platform", "")).strip()
        platform_user_id = str(payload.get("platform_user_id", "")).strip()
        platform_username = str(payload.get("platform_username", "")).strip()
        oathweaver_user_id = str(payload.get("oathweaver_user_id", "")).strip()
        if not platform or not platform_user_id or not oathweaver_user_id:
            return {"ok": False, "error": "platform, platform_user_id, and oathweaver_user_id are required."}, 400
        conv_store = ConversationStore(ctx.root, oathweaver_user_id)
        conv = conv_store.create(title=f"{platform.capitalize()} conversation", project="general")
        mapping = BotUserStore(ctx.root).create_mapping(
            platform=platform,
            platform_user_id=platform_user_id,
            platform_username=platform_username or platform_user_id,
            oathweaver_user_id=oathweaver_user_id,
            conversation_id=conv["id"],
        )
        return {"ok": True, "mapping": mapping}, 200

    @bp.route("/api/owner/bot-users/<mapping_id>", methods=["DELETE"])
    def delete_bot_user(mapping_id: str) -> tuple[dict, int]:
        from bots.bot_user_store import BotUserStore

        profile = ctx.require_profile()
        if not bool(profile.get("is_owner", False)):
            return {"ok": False, "error": "Owner only."}, 403
        deleted = BotUserStore(ctx.root).delete_mapping(mapping_id)
        if not deleted:
            return {"ok": False, "error": "Not found."}, 404
        return {"ok": True}, 200

    @bp.route("/api/owner/bot-users/pending", methods=["GET"])
    def get_bot_pending() -> tuple[dict, int]:
        profile = ctx.require_profile()
        if not bool(profile.get("is_owner", False)):
            return {"ok": False, "error": "Owner only."}, 403
        pending: list[dict] = []
        try:
            from bots.telegram_bot import get_pending_unauthorized as _tg_pending
            pending.extend(_tg_pending())
        except Exception as exc:
            pending.append({"platform": "telegram", "error": f"pending queue unavailable: {exc}"})
        try:
            from bots.discord_bot import get_pending_unauthorized as _dc_pending
            pending.extend(_dc_pending())
        except Exception as exc:
            pending.append({"platform": "discord", "error": f"pending queue unavailable: {exc}"})
        return {"ok": True, "pending": pending}, 200

    @bp.route("/api/memory/topics", methods=["GET"])
    def get_memory_topics() -> tuple[dict, int]:
        from shared_tools.topic_memory import TopicMemory

        ctx.require_profile()
        return {"ok": True, "topics": TopicMemory(ctx.root).list_topics()}, 200

    @bp.route("/api/memory/topics/<topic_key>", methods=["GET"])
    def get_memory_topic(topic_key: str) -> tuple[dict, int]:
        from shared_tools.topic_memory import TopicMemory

        ctx.require_profile()
        topic = TopicMemory(ctx.root).get_topic(topic_key)
        if not topic:
            return {"ok": False, "error": "Not found."}, 404
        return {"ok": True, "topic": topic}, 200

    @bp.route("/api/memory/reviews/<review_id>/answer", methods=["POST"])
    def answer_memory_review(review_id: str) -> tuple[dict, int]:
        from shared_tools.topic_memory import TopicMemory

        ctx.require_profile()
        payload = request.get_json(silent=True) or {}
        accepted = bool(payload.get("accepted", False))
        ok = TopicMemory(ctx.root).answer_review(review_id, accepted)
        if not ok:
            return {"ok": False, "error": "Review not found or already answered."}, 404
        return {"ok": True}, 200

    @bp.route("/api/system/reset-environment", methods=["POST"])
    def reset_environment() -> tuple[dict, int]:
        import shutil as _shutil

        from infra.persistence.migration_helpers import clear_structured_runtime_state

        profile = ctx.require_profile()
        if not bool(profile.get("is_owner", False)):
            return {"ok": False, "error": "Owner only."}, 403
        payload = request.get_json(silent=True) or {}
        if str(payload.get("confirm", "")).strip() != "RESET":
            return {"ok": False, "error": 'Pass {"confirm": "RESET"} to confirm.'}, 400

        log: list[str] = []
        runtime_root = ctx.root / "Runtime"
        projects_root = ctx.root / "Projects"

        def _write_json(path: Path, value: Any) -> None:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(json.dumps(value, indent=2), encoding="utf-8")
            log.append(f"reset  {path.relative_to(ctx.root)}")

        def _wipe_dir(path: Path) -> None:
            if not path.exists():
                return
            for child in path.iterdir():
                if child.name == ".gitkeep":
                    continue
                if child.is_dir():
                    _shutil.rmtree(child)
                else:
                    child.unlink()
            log.append(f"wiped  {path.relative_to(ctx.root)}/")

        def _truncate(path: Path) -> None:
            if path.exists():
                path.write_text("", encoding="utf-8")
                log.append(f"clear  {path.relative_to(ctx.root)}")

        def _delete(path: Path) -> None:
            if path.exists():
                path.unlink()
                log.append(f"del    {path.relative_to(ctx.root)}")

        try:
            for path in [
                runtime_root / "topics" / "topics.json",
                runtime_root / "learning" / "lessons.json",
                runtime_root / "learning" / "reflections.json",
                runtime_root / "routines" / "routines.json",
                runtime_root / "cloud" / "pending_requests.json",
                runtime_root / "web" / "pending_requests.json",
            ]:
                _write_json(path, [])

            for path in [
                runtime_root / "learning" / "continuous_improvement.json",
                runtime_root / "memory" / "project_context.json",
                runtime_root / "watchtower" / "briefing_state.json",
            ]:
                _write_json(path, {})

            _write_json(runtime_root / "project_pipeline.json", {"projects": {}})
            _write_json(runtime_root / "watchtower" / "watches.json", [])
            _write_json(runtime_root / "family" / "accounts.json", {"accounts": [], "created_at": "", "updated_at": ""})
            clear_structured_runtime_state(ctx.root)
            log.append("reset  Runtime/state/oathweaver.db tables")

            for path in [
                runtime_root / "conversations",
                runtime_root / "briefings",
                runtime_root / "activity",
                runtime_root / "approvals" / "decided",
                runtime_root / "approvals" / "pending",
                runtime_root / "handoff" / "pending",
                runtime_root / "handoff" / "denied",
                runtime_root / "artifacts",
                runtime_root / "logs",
                runtime_root / "memory" / "personal",
                runtime_root / "memory" / "projects",
                runtime_root / "attachments",
            ]:
                _wipe_dir(path)

            if (runtime_root / "handoff").exists():
                for target_dir in (runtime_root / "handoff").iterdir():
                    if not target_dir.is_dir():
                        continue
                    for sub in ("inbox", "outbox", "outbox_processed"):
                        _wipe_dir(target_dir / sub)

            if (runtime_root / "users").exists():
                for user_dir in (runtime_root / "users").iterdir():
                    if user_dir.is_dir():
                        _shutil.rmtree(user_dir)
                        log.append(f"wiped  users/{user_dir.name}/")

            for path in [
                runtime_root / "activity" / "events.jsonl",
                runtime_root / "cloud" / "runs.jsonl",
                runtime_root / "web" / "sources.jsonl",
            ]:
                _truncate(path)

            for path in [
                runtime_root / "web" / "session_secret.txt",
                runtime_root / "web" / "_tmp_test.txt",
                runtime_root / "project_catalog.json",
            ]:
                _delete(path)

            _wipe_dir(projects_root)

        except Exception as exc:
            return {"ok": False, "error": str(exc), "log": log}, 500

        log.append("Reset complete.")
        return {"ok": True, "log": log}, 200
