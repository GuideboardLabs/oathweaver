from __future__ import annotations

import urllib.request
from pathlib import Path
from typing import TYPE_CHECKING, Any

from flask import Blueprint, abort, render_template, send_from_directory

from shared_tools.optional_features import optional_feature_status
from shared_tools.phase0 import enrich_phase0_aliases
from web_gui.routes.system_support import _STATIC_DIR, asset_versions, guess_mime_from_ext

if TYPE_CHECKING:
    from web_gui.app_context import AppContext


def register_health_routes(bp: Blueprint, ctx: AppContext) -> None:
    @bp.route("/", methods=["GET"])
    def index() -> str:
        asset_v, vendor_v = asset_versions()
        return render_template("index.html", asset_v=asset_v, vendor_v=vendor_v)

    @bp.route("/manifest.webmanifest", methods=["GET"])
    def manifest() -> Any:
        return send_from_directory(str(_STATIC_DIR), "manifest.webmanifest", mimetype="application/manifest+json")

    @bp.route("/service-worker.js", methods=["GET"])
    def service_worker() -> Any:
        response = send_from_directory(str(_STATIC_DIR), "service-worker.js", mimetype="application/javascript")
        response.headers["Service-Worker-Allowed"] = "/"
        response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
        response.headers["Pragma"] = "no-cache"
        response.headers["Expires"] = "0"
        return response

    @bp.route("/api/health", methods=["GET"])
    def health_check() -> tuple[dict, int]:
        checks: dict[str, object] = {}
        try:
            req = urllib.request.Request("http://127.0.0.1:11434/api/tags", method="GET")
            with urllib.request.urlopen(req, timeout=2) as resp:
                checks["ollama"] = "ok" if resp.status == 200 else "degraded"
        except Exception:
            checks["ollama"] = "unreachable"
        try:
            req = urllib.request.Request("http://127.0.0.1:8080/", method="GET")
            with urllib.request.urlopen(req, timeout=2) as resp:
                checks["searxng"] = "ok" if resp.status == 200 else "degraded"
        except Exception:
            checks["searxng"] = "unreachable"
        try:
            req = urllib.request.Request("http://127.0.0.1:11235/health", method="GET")
            with urllib.request.urlopen(req, timeout=2) as resp:
                checks["crawl4ai"] = "ok" if resp.status == 200 else "degraded"
        except Exception:
            checks["crawl4ai"] = "unreachable"
        try:
            import psutil
            checks["disk_free_gb"] = round(psutil.disk_usage("/").free / (1024**3), 1)
            checks["memory_percent"] = psutil.virtual_memory().percent
        except Exception:
            pass
        wt = ctx.get_watchtower()
        checks["watchtower"] = "running" if (wt and hasattr(wt, "_thread") and getattr(wt._thread, "is_alive", lambda: False)()) else "stopped"
        checks["requirements_lock"] = "present" if (ctx.root / "requirements.lock").exists() else "missing"
        checks["optional_features"] = optional_feature_status()
        overall = "ok" if checks.get("ollama") == "ok" else "degraded"
        return {"ok": True, "status": overall, "checks": checks}, 200

    @bp.route("/api/panel/status", methods=["GET"])
    def panel_status() -> tuple[dict, int]:
        from web_gui.routes.projects import _project_panel_rows

        profile = ctx.require_profile()
        cache_scope = str(profile.get("id", ""))

        def _build() -> dict:
            orch = ctx.new_orch(profile)
            monitored = orch.handoff_queue.monitor_threads(limit=500)
            waiting_output = len([x for x in monitored if str(x.get("status", "")) == "waiting_output"])
            ready_for_ingest = len([x for x in monitored if str(x.get("status", "")) == "ready_for_ingest"])
            project_rows = _project_panel_rows(ctx, orch, limit=200)
            pending_actions_count = len(orch.pending_actions_data(limit=500))
            foraging = ctx.foraging_manager.snapshot(profile_id=str(profile.get("id", "")))
            building = ctx.building_manager.snapshot(profile_id=str(profile.get("id", "")))
            try:
                wt_local = ctx.get_watchtower()
                cards_unread = wt_local.unread_count()
                watchtower_active = len([w for w in (wt_local.list_watches() if hasattr(wt_local, "list_watches") else []) if w.get("enabled", True)])
                action_proposals_pending = len(orch.approval_gate.list_action_proposals(limit=500))
            except Exception:
                cards_unread = 0
                watchtower_active = 0
                action_proposals_pending = 0
            try:
                te = ctx.get_topic_engine()
                all_topics = te.list_topics()
                topics_with_research = 0
                for row in all_topics:
                    slug = str(row.get("slug", "")).strip()
                    if slug:
                        summary_dir = ctx.root / "Projects" / slug / "research_summaries"
                        if summary_dir.exists() and any(summary_dir.glob("*.md")):
                            topics_with_research += 1
            except Exception:
                topics_with_research = 0
            try:
                library_counts = ctx.library_service_for(profile).counts()
            except Exception:
                library_counts = {"total": 0, "pending": 0}
            try:
                external_mode = orch.external_tools_settings.get_mode()
            except Exception:
                external_mode = "off"
            open_external_requests = 0
            if external_mode != "off":
                try:
                    open_external_requests = len(orch.external_request_store.list_open(limit=500))
                except Exception:
                    open_external_requests = 0
            return {
                "pending_actions": pending_actions_count,
                "open_reflections": orch.reflection_engine.count_open(),
                "learned_lessons": orch.learning_engine.count_lessons(),
                "open_web_requests": len(orch.web_engine.list_pending(limit=500)),
                "web_mode": orch.web_engine.get_mode(),
                "open_cloud_requests": 0,
                "cloud_mode": "off",
                "open_external_requests": open_external_requests,
                "external_tools_mode": external_mode,
                "pending_handoffs": len(monitored),
                "handoff_waiting_output": waiting_output,
                "handoff_ready_for_ingest": ready_for_ingest,
                "active_projects": len(project_rows),
                "foraging_paused": bool(foraging.get("paused", False)),
                "foraging_active_jobs": int(foraging.get("active_jobs", 0)),
                "foraging_yielding": bool(foraging.get("yielding", False)),
                "foraging_completion_unread": bool(foraging.get("completion_unread", False)),
                "foraging_last_completed_at": str(foraging.get("last_completed_at", "")).strip(),
                "foraging_updated_at": str(foraging.get("updated_at", "")).strip(),
                "building_paused": bool(building.get("paused", False)),
                "building_active_jobs": int(building.get("active_jobs", 0)),
                "building_completion_unread": bool(building.get("completion_unread", False)),
                "building_last_completed_at": str(building.get("last_completed_at", "")).strip(),
                "building_updated_at": str(building.get("updated_at", "")).strip(),
                "cards_unread": cards_unread,
                "action_proposals_pending": action_proposals_pending,
                "watchtower_active": watchtower_active,
                "topics_with_research": topics_with_research,
                "forage_cards_pinned": ctx.forage_cards_pinned_count(),
                "library_items_total": int(library_counts.get("total", 0)),
                "library_items_pending": int(library_counts.get("pending", 0)),
            }

        payload = ctx.cache_get(cache_scope, "panel_status", ttl_sec=1.5, build_fn=_build)
        payload = enrich_phase0_aliases(payload)
        return payload, 200

    @bp.route("/api/foraging/state", methods=["GET"])
    def foraging_state_api() -> tuple[dict, int]:
        profile = ctx.require_profile()
        snapshot = ctx.foraging_manager.snapshot(profile_id=str(profile.get("id", "")))
        return enrich_phase0_aliases({"ok": True, **snapshot}), 200

    @bp.route("/api/research/state", methods=["GET"])
    def research_state_api() -> tuple[dict, int]:
        profile = ctx.require_profile()
        snapshot = ctx.foraging_manager.snapshot(profile_id=str(profile.get("id", "")))
        return enrich_phase0_aliases({"ok": True, **snapshot}), 200

    @bp.route("/api/home/companion-images", methods=["GET"])
    def home_companion_images_list() -> tuple[dict, int]:
        folder = ctx.root / "Images" / "HomePageCompanion"
        if not folder.exists():
            return {"images": []}, 200
        allowed = {".jpg", ".jpeg", ".png", ".gif", ".webp", ".svg", ".avif"}
        images = sorted(f.name for f in folder.iterdir() if f.is_file() and f.suffix.lower() in allowed)
        return {"images": images}, 200

    @bp.route("/api/home/companion-images/<filename>", methods=["GET"])
    def home_companion_image_file(filename: str) -> Any:
        raw = str(filename or "").strip()
        if not raw or "/" in raw or "\\" in raw:
            abort(404)
        folder = ctx.root / "Images" / "HomePageCompanion"
        path = folder / raw
        if not path.exists() or not path.is_file():
            abort(404)
        return send_from_directory(str(folder), raw, as_attachment=False, mimetype=guess_mime_from_ext(path.suffix))
