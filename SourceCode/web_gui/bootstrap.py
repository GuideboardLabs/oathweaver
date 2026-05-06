from __future__ import annotations

import json
import logging
import threading
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any

from flask import Flask

LOGGER = logging.getLogger(__name__)


def _collect_routing_models(repo_root: Path) -> set[str]:
    """Walk model_routing.json and return every model name referenced."""
    config_path = repo_root / "SourceCode" / "configs" / "model_routing.json"
    if not config_path.exists():
        return set()
    try:
        data = json.loads(config_path.read_text(encoding="utf-8"))
    except Exception:
        return set()

    models: set[str] = set()

    def _walk(node: Any) -> None:
        if isinstance(node, dict):
            for k, v in node.items():
                if k == "model" and isinstance(v, str) and v.strip():
                    models.add(v.strip())
                elif k in ("fallback_models", "synthesis_fallback_models") and isinstance(v, list):
                    for item in v:
                        if isinstance(item, str) and item.strip():
                            models.add(item.strip())
                else:
                    _walk(v)
        elif isinstance(node, list):
            for item in node:
                _walk(item)

    _walk(data)
    return models


def check_model_availability(repo_root: Path, logger: Any = None) -> None:
    """Log a warning for each model in model_routing.json that is not pulled in Ollama."""
    log = logger or LOGGER
    required = _collect_routing_models(repo_root)
    if not required:
        return
    try:
        from shared_tools.ollama_client import OllamaClient
        installed_raw = OllamaClient().list_local_models()
        # Normalise: Ollama often returns "model:tag"; also compare base name
        installed: set[str] = set()
        for name in installed_raw:
            installed.add(name.lower())
            installed.add(name.split(":")[0].lower())
        missing = sorted(m for m in required if m.lower() not in installed and m.split(":")[0].lower() not in installed)
        if missing:
            for m in missing:
                log.warning("Model not found in Ollama — pull it before use: %s", m)
        else:
            log.info("Model health check passed: all %d routing models are present.", len(required))
    except Exception as exc:
        log.warning("Model health check skipped (Ollama not reachable?): %s", exc)

_watchtower = None
_watchtower_lock = threading.Lock()
_watchtower_root: Path | None = None
_topic_engine = None
_topic_engine_lock = threading.Lock()
_topic_engine_root: Path | None = None
_digest_scheduler: "DailyDigestScheduler | None" = None
_digest_scheduler_lock = threading.Lock()
_digest_scheduler_root: Path | None = None


# ---------------------------------------------------------------------------
# Watchtower → Web Push bridge
# ---------------------------------------------------------------------------

def _register_watchtower_push_listener(repo_root: Path) -> None:
    """Subscribe to watchtower watch_completed events and fire web push."""
    try:
        from shared_tools.activity_bus import ActivityBus
        bus = ActivityBus(repo_root)

        def _on_watch_completed(data: dict) -> None:
            try:
                watch_id = str(data.get("watch_id", "")).strip()
                card_id = str(data.get("card_id", data.get("briefing_id", ""))).strip()
                wt = get_watchtower(repo_root)
                card = wt.get_research_card(card_id) if card_id else None
                topic = str((card or {}).get("topic", "Oathweaver Watch")).strip() or "Oathweaver Watch"
                preview = str((card or {}).get("preview", "")).strip()
                body = (preview[:200] + "…") if len(preview) > 200 else preview or "New research card ready."

                from shared_tools.web_push import send_notification
                # Send to all known users (typically just the owner for a home setup)
                users_dir = repo_root / "Runtime" / "users"
                user_ids: list[str] = []
                if users_dir.is_dir():
                    user_ids = [d.name for d in users_dir.iterdir() if d.is_dir() and (d / "web_push.json").exists()]
                if not user_ids:
                    user_ids = ["owner"]
                for uid in user_ids:
                    try:
                        send_notification(
                            repo_root,
                            uid,
                            {"title": f"Research Card: {topic}", "body": body, "icon": "/static/icons/icon-192.png"},
                            event_key=f"watch_{card_id or watch_id}",
                        )
                    except Exception:
                        LOGGER.exception("Watchtower web push delivery failed for user %s.", uid)
            except Exception:
                LOGGER.exception("Watchtower push notification failed.")

        def _listener(row: dict[str, Any]) -> None:
            if str(row.get("actor", "")).strip() != "watchtower":
                return
            if str(row.get("event", "")).strip() != "watch_completed":
                return
            details = row.get("details") or {}
            if isinstance(details, dict):
                _on_watch_completed(details)

        bus.subscribe(_listener)
        LOGGER.info("Watchtower → web push bridge registered.")
    except Exception:
        LOGGER.exception("Failed to register watchtower push listener.")


# ---------------------------------------------------------------------------
# Daily Digest Scheduler
# ---------------------------------------------------------------------------

class DailyDigestScheduler(threading.Thread):
    """Background thread that fires a morning digest push at a configurable hour."""

    def __init__(self, repo_root: Path) -> None:
        super().__init__(daemon=True, name="DailyDigestScheduler")
        self.repo_root = repo_root
        self._stop = threading.Event()

    def stop(self) -> None:
        self._stop.set()

    def run(self) -> None:
        while not self._stop.wait(60):
            try:
                self._tick()
            except Exception:
                LOGGER.exception("DailyDigestScheduler tick error.")

    def _tick(self) -> None:
        cfg = self._load_config()
        if not cfg.get("morning_digest_enabled", False):
            return
        hour = int(cfg.get("morning_digest_hour", 7))
        now = datetime.now(timezone.utc)
        # Use local time for the hour check if possible, fallback to UTC
        try:
            import time as _time
            local_now = datetime.fromtimestamp(_time.time())
            current_hour = local_now.hour
            today_str = local_now.strftime("%Y-%m-%d")
        except Exception:
            current_hour = now.hour
            today_str = now.strftime("%Y-%m-%d")

        if current_hour != hour:
            return

        last_run_path = self.repo_root / "Runtime" / "state" / "daily_digest_last_run.txt"
        if last_run_path.exists():
            try:
                if last_run_path.read_text().strip() == today_str:
                    return  # already ran today
            except Exception:
                pass

        # Mark as run before firing (prevent double-send if push is slow)
        last_run_path.parent.mkdir(parents=True, exist_ok=True)
        last_run_path.write_text(today_str)

        self._send_digest(cfg)

    def _load_config(self) -> dict:
        cfg_path = self.repo_root / "Runtime" / "config" / "oathweaver_settings.json"
        if not cfg_path.exists():
            return {}
        try:
            data = json.loads(cfg_path.read_text(encoding="utf-8"))
            return data if isinstance(data, dict) else {}
        except Exception:
            return {}

    def _send_digest(self, cfg: dict) -> None:
        try:
            from shared_tools.daily_digest import build_digest
            from shared_tools.web_push import send_notification
        except ImportError:
            LOGGER.warning("daily_digest or web_push not available, skipping digest.")
            return

        try:
            digest_text = build_digest(self.repo_root)
            if not digest_text.strip():
                return
            users_dir = self.repo_root / "Runtime" / "users"
            user_ids: list[str] = []
            if users_dir.is_dir():
                user_ids = [d.name for d in users_dir.iterdir() if d.is_dir() and (d / "web_push.json").exists()]
            if not user_ids:
                user_ids = ["owner"]
            for uid in user_ids:
                try:
                    send_notification(
                        self.repo_root,
                        uid,
                        {"title": "Good morning — your daily digest", "body": digest_text[:200], "icon": "/static/icons/icon-192.png"},
                        event_key=f"digest_{date.today().isoformat()}",
                    )
                except Exception:
                    LOGGER.exception("Daily digest push delivery failed for user %s.", uid)
        except Exception:
            LOGGER.exception("Daily digest send failed.")


def _fix_runtime_permissions(repo_root: Path) -> None:
    """Ensure sensitive runtime files and the Runtime directory are not world-readable."""
    runtime = repo_root / "Runtime"
    sensitive_files = [
        runtime / "web" / "session_secret.txt",
        runtime / "cloud" / "settings.json",
        runtime / "config" / "bot_config.json",
        runtime / "state" / "oathweaver.db",
        runtime / "oathweaver.db",
    ]
    for p in sensitive_files:
        if p.exists():
            try:
                p.chmod(0o600)
            except OSError:
                pass
    if runtime.exists():
        try:
            runtime.chmod(0o700)
        except OSError:
            pass


def get_watchtower(repo_root: Path):
    global _watchtower, _watchtower_root
    with _watchtower_lock:
        if _watchtower is None or _watchtower_root != repo_root:
            from shared_tools.watchtower import WatchtowerEngine
            _watchtower = WatchtowerEngine(repo_root)
            _watchtower_root = repo_root
    return _watchtower


def get_topic_engine(repo_root: Path):
    global _topic_engine, _topic_engine_root
    with _topic_engine_lock:
        if _topic_engine is None or _topic_engine_root != repo_root:
            from shared_tools.topic_engine import TopicEngine
            _topic_engine = TopicEngine(repo_root)
            _topic_engine_root = repo_root
    return _topic_engine


def _start_bots_safe(repo_root: Path) -> None:
    try:
        from bots.bot_runner import start_bots
        start_bots(repo_root)
    except Exception:
        LOGGER.exception("Failed to start messaging bots.")


def ensure_background_services_started(repo_root: Path, app: Flask | None = None) -> None:
    global _digest_scheduler, _digest_scheduler_root
    _fix_runtime_permissions(repo_root)
    logger = getattr(app, "logger", LOGGER)
    if app is not None:
        with app.app_context():
            state = app.extensions.setdefault("oathweaver_background_services", {"started": False})
            if state.get("started"):
                return
            try:
                get_watchtower(repo_root).start_background_thread()
            except Exception:
                logger.exception("Failed to initialize Oathweaver background services.")
                raise
            state["started"] = True
            threading.Thread(
                target=check_model_availability,
                args=(repo_root, logger),
                daemon=True,
            ).start()
            threading.Thread(
                target=_register_watchtower_push_listener,
                args=(repo_root,),
                daemon=True,
            ).start()
            with _digest_scheduler_lock:
                if _digest_scheduler is not None and _digest_scheduler_root != repo_root:
                    _digest_scheduler.stop()
                    _digest_scheduler = None
                if _digest_scheduler is None:
                    _digest_scheduler = DailyDigestScheduler(repo_root)
                    _digest_scheduler_root = repo_root
                    _digest_scheduler.start()
            threading.Thread(
                target=_start_bots_safe,
                args=(repo_root,),
                daemon=True,
                name="oathweaver-bots",
            ).start()
            return

    get_watchtower(repo_root).start_background_thread()
    threading.Thread(
        target=check_model_availability,
        args=(repo_root,),
        daemon=True,
    ).start()
    threading.Thread(
        target=_register_watchtower_push_listener,
        args=(repo_root,),
        daemon=True,
    ).start()
    with _digest_scheduler_lock:
        if _digest_scheduler is not None and _digest_scheduler_root != repo_root:
            _digest_scheduler.stop()
            _digest_scheduler = None
        if _digest_scheduler is None:
            _digest_scheduler = DailyDigestScheduler(repo_root)
            _digest_scheduler_root = repo_root
            _digest_scheduler.start()
    threading.Thread(
        target=_start_bots_safe,
        args=(repo_root,),
        daemon=True,
        name="oathweaver-bots",
    ).start()


def background_state() -> dict[str, Any]:
    return {
        "watchtower": _watchtower,
        "topic_engine": _topic_engine,
    }
