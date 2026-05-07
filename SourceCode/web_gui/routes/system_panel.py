from __future__ import annotations

from datetime import datetime, timezone
from typing import TYPE_CHECKING

from flask import Blueprint, request

if TYPE_CHECKING:
    from web_gui.app_context import AppContext


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _safe_agent_label(raw: object) -> str:
    text = str(raw or "").strip()
    if not text:
        return "Agent"
    return text.replace("_", " ")


def _safe_node_id(raw: object, *, fallback: str) -> str:
    text = str(raw or "").strip()
    if text:
        return text
    return fallback


def register_panel_routes(bp: Blueprint, ctx: AppContext) -> None:
    @bp.get("/api/panel/reflections")
    def panel_reflections() -> tuple[dict, int]:
        from web_gui.utils.request_utils import parse_optional_int

        profile = ctx.require_profile()
        limit = parse_optional_int(request.args.get("limit"), default=20, minimum=1, maximum=200)
        orch = ctx.new_orch(profile)
        rows = orch.reflection_engine.list_open(limit=limit)
        return {"reflections": rows}, 200

    @bp.get("/api/panel/reflections-history")
    def panel_reflections_history() -> tuple[dict, int]:
        from web_gui.utils.request_utils import parse_optional_int

        profile = ctx.require_profile()
        limit = parse_optional_int(request.args.get("limit"), default=80, minimum=1, maximum=300)
        orch = ctx.new_orch(profile)
        rows = orch.reflection_engine.list_history(limit=limit)
        return {"reflections": rows}, 200

    @bp.get("/api/panel/lessons")
    def panel_lessons() -> tuple[dict, int]:
        from web_gui.utils.request_utils import parse_optional_int

        profile = ctx.require_profile()
        lane = str(request.args.get("lane", "")).strip() or None
        limit = parse_optional_int(request.args.get("limit"), default=25, minimum=1, maximum=200)
        sort_by = str(request.args.get("sort", "newest")).strip().lower() or "newest"
        orch = ctx.new_orch(profile)
        rows = orch.learning_engine.list_lessons(lane=lane, limit=limit, sort_by=sort_by)
        return {"lessons": rows}, 200

    @bp.post("/api/lessons/<lesson_id>/approve")
    def lesson_approve(lesson_id: str) -> tuple[dict, int]:
        profile = ctx.require_profile()
        orch = ctx.new_orch(profile)
        approved_by = str(profile.get("username", "")).strip() or "owner"
        row = orch.learning_engine.approve_lesson(lesson_id=lesson_id, approved_by=approved_by)
        if row is None:
            return {"ok": False, "message": "Lesson not found."}, 404
        if bool(row.get("policy_blocked", False)):
            return {"ok": False, "message": str(row.get("policy_message", "Lesson cannot be approved.")), "lesson": row}, 400
        return {"ok": True, "message": "Lesson approved.", "lesson": row}, 200

    @bp.post("/api/lessons/<lesson_id>/reject")
    def lesson_reject(lesson_id: str) -> tuple[dict, int]:
        profile = ctx.require_profile()
        orch = ctx.new_orch(profile)
        rejected_by = str(profile.get("username", "")).strip() or "owner"
        row = orch.learning_engine.reject_lesson(lesson_id=lesson_id, rejected_by=rejected_by)
        if row is None:
            return {"ok": False, "message": "Lesson not found."}, 404
        return {"ok": True, "message": "Lesson rejected.", "lesson": row}, 200

    @bp.post("/api/lessons/<lesson_id>/expire")
    def lesson_expire(lesson_id: str) -> tuple[dict, int]:
        profile = ctx.require_profile()
        orch = ctx.new_orch(profile)
        row = orch.learning_engine.expire_lesson(lesson_id=lesson_id)
        if row is None:
            return {"ok": False, "message": "Lesson not found."}, 404
        return {"ok": True, "message": "Lesson expired.", "lesson": row}, 200

    @bp.get("/api/panel/handoffs")
    def panel_handoffs() -> tuple[dict, int]:
        from web_gui.utils.request_utils import parse_optional_int

        profile = ctx.require_profile()
        limit = parse_optional_int(request.args.get("limit"), default=20, minimum=1, maximum=200)
        orch = ctx.new_orch(profile)
        rows = orch.handoff_queue.monitor_threads(limit=limit)
        return {"handoffs": rows}, 200

    @bp.get("/api/panel/outbox")
    def panel_outbox() -> tuple[dict, int]:
        from web_gui.utils.request_utils import parse_optional_int

        profile = ctx.require_profile()
        limit = parse_optional_int(request.args.get("limit"), default=40, minimum=1, maximum=300)
        orch = ctx.new_orch(profile)
        rows = orch.handoff_queue.monitor_threads(limit=500)
        outbox_rows = [row for row in rows if str(row.get("outbox_path", "")).strip()]
        outbox_rows.sort(key=lambda row: str(row.get("created_at", "")), reverse=True)
        return {"outbox": outbox_rows[:limit]}, 200

    @bp.get("/api/panel/projects")
    def panel_projects() -> tuple[dict, int]:
        from web_gui.routes.projects import _project_panel_rows
        from web_gui.utils.request_utils import parse_optional_int

        profile = ctx.require_profile()
        cache_scope = str(profile.get("id", ""))
        limit = parse_optional_int(request.args.get("limit"), default=40, minimum=1, maximum=200)
        orch = ctx.new_orch(profile)
        rows = ctx.cache_get(
            cache_scope,
            f"panel_projects:{limit}",
            ttl_sec=2.0,
            build_fn=lambda: _project_panel_rows(ctx, orch, limit=limit),
        )
        return {"projects": rows}, 200

    @bp.get("/api/panel/foraging")
    def panel_foraging() -> tuple[dict, int]:
        from web_gui.utils.request_utils import parse_optional_int

        profile = ctx.require_profile()
        profile_id = str(profile.get("id", ""))
        limit = parse_optional_int(request.args.get("limit"), default=60, minimum=1, maximum=200)
        mark_read = str(request.args.get("mark_read", "")).strip().lower() in {"1", "true", "yes", "on"}
        if mark_read:
            ctx.foraging_manager.mark_completion_read(profile_id=profile_id)
            ctx.cache_clear(profile_id)
        snapshot = ctx.foraging_manager.snapshot(profile_id=profile_id)
        jobs = ctx.foraging_manager.rows_for_profile(profile, ctx.job_manager, limit=limit)
        return {"foraging": snapshot, "jobs": jobs}, 200

    @bp.get("/api/panel/building")
    def panel_building() -> tuple[dict, int]:
        from web_gui.utils.request_utils import parse_optional_int

        profile = ctx.require_profile()
        profile_id = str(profile.get("id", ""))
        limit = parse_optional_int(request.args.get("limit"), default=60, minimum=1, maximum=200)
        mark_read = str(request.args.get("mark_read", "")).strip().lower() in {"1", "true", "yes", "on"}
        if mark_read:
            ctx.building_manager.mark_completion_read(profile_id=profile_id)
            ctx.cache_clear(profile_id)
        snapshot = ctx.building_manager.snapshot(profile_id=profile_id)
        jobs = ctx.building_manager.rows_for_profile(profile, ctx.job_manager, limit=limit)
        return {"building": snapshot, "jobs": jobs}, 200

    @bp.get("/api/panel/agent-graph")
    def panel_agent_graph() -> tuple[dict, int]:
        profile = ctx.require_profile()
        profile_id = str(profile.get("id", "")).strip()
        foraging_jobs = ctx.foraging_manager.rows_for_profile(profile, ctx.job_manager, limit=120)
        building_jobs = ctx.building_manager.rows_for_profile(profile, ctx.job_manager, limit=120)

        nodes_by_id: dict[str, dict] = {}
        edges: list[dict] = []
        seen_edges: set[tuple[str, str, str]] = set()

        def add_node(
            *,
            node_id: str,
            label: str,
            kind: str,
            lane: str = "",
            status: str = "active",
            subtitle: str = "",
            meta: dict | None = None,
        ) -> None:
            safe_id = _safe_node_id(node_id, fallback=f"{kind}:{len(nodes_by_id) + 1}")
            row = {
                "id": safe_id,
                "label": str(label or "").strip() or kind.title(),
                "kind": str(kind or "node").strip().lower(),
                "lane": str(lane or "").strip().lower(),
                "status": str(status or "active").strip().lower(),
                "subtitle": str(subtitle or "").strip(),
                "meta": meta if isinstance(meta, dict) else {},
            }
            if safe_id in nodes_by_id:
                # Keep existing position anchor but merge latest metadata.
                existing = nodes_by_id[safe_id]
                existing.update({k: v for k, v in row.items() if k != "meta"})
                existing_meta = existing.get("meta", {})
                if not isinstance(existing_meta, dict):
                    existing_meta = {}
                existing_meta.update(row["meta"])
                existing["meta"] = existing_meta
                return
            nodes_by_id[safe_id] = row

        def add_edge(source: str, target: str, *, label: str = "") -> None:
            src = _safe_node_id(source, fallback="")
            dst = _safe_node_id(target, fallback="")
            if not src or not dst:
                return
            safe_label = str(label or "").strip()
            key = (src, dst, safe_label)
            if key in seen_edges:
                return
            seen_edges.add(key)
            edges.append({"source": src, "target": dst, "label": safe_label})

        root_id = "node:orch"
        add_node(
            node_id=root_id,
            label="Overseer Orchestrator",
            kind="root",
            status="active",
            subtitle="Top-level orchestration",
            meta={
                "profile_id": profile_id or "owner",
                "scope": "system",
            },
        )

        lane_foraging_id = "lane:foraging"
        lane_building_id = "lane:building"
        add_node(
            node_id=lane_foraging_id,
            label="Research / Forage",
            kind="lane",
            lane="foraging",
            status="active" if foraging_jobs else "idle",
            subtitle=f"{len(foraging_jobs)} active job(s)",
            meta={"lane": "foraging"},
        )
        add_node(
            node_id=lane_building_id,
            label="Make / Build",
            kind="lane",
            lane="building",
            status="active" if building_jobs else "idle",
            subtitle=f"{len(building_jobs)} active job(s)",
            meta={"lane": "building"},
        )
        add_edge(root_id, lane_foraging_id, label="dispatch")
        add_edge(root_id, lane_building_id, label="dispatch")

        foraging_active_agents = 0
        building_active_agents = 0

        def _add_job_group(rows: list[dict], *, lane_name: str, lane_node_id: str) -> int:
            active_count = 0
            for row in rows:
                if not isinstance(row, dict):
                    continue
                request_id = str(row.get("id", "")).strip()
                if not request_id:
                    continue
                project = str(row.get("project", "")).strip() or "general"
                stage = str(row.get("stage", "")).strip() or "running"
                status = str(row.get("status", "")).strip() or "running"
                conversation_id = str(row.get("conversation_id", "")).strip()
                started_at = str(row.get("started_at", "")).strip()
                updated_at = str(row.get("updated_at", "")).strip()
                tracker = row.get("agent_tracker", {})
                if not isinstance(tracker, dict):
                    tracker = {}
                active_agents = tracker.get("active", [])
                if not isinstance(active_agents, list):
                    active_agents = []

                job_node_id = f"job:{lane_name}:{request_id}"
                add_node(
                    node_id=job_node_id,
                    label=f"{project}",
                    kind="job",
                    lane=lane_name,
                    status=status,
                    subtitle=f"{stage} | {len(active_agents)} active agent(s)",
                    meta={
                        "request_id": request_id,
                        "project": project,
                        "conversation_id": conversation_id,
                        "stage": stage,
                        "status": status,
                        "started_at": started_at,
                        "updated_at": updated_at,
                        "lane": lane_name,
                    },
                )
                add_edge(lane_node_id, job_node_id, label="job")

                for idx, item in enumerate(active_agents):
                    if isinstance(item, dict):
                        persona = str(item.get("persona", "")).strip()
                        role = str(item.get("role", "")).strip()
                        model = str(item.get("model", "")).strip()
                        directive = str(item.get("directive", "")).strip()
                    else:
                        persona = str(item or "").strip()
                        role = ""
                        model = ""
                        directive = ""
                    if not persona:
                        persona = f"agent-{idx + 1}"
                    persona_label = _safe_agent_label(persona)
                    persona_key = "".join(ch if ch.isalnum() else "_" for ch in persona).strip("_") or f"agent_{idx + 1}"
                    agent_node_id = f"agent:{lane_name}:{request_id}:{idx + 1}:{persona_key}"
                    add_node(
                        node_id=agent_node_id,
                        label=persona_label,
                        kind="agent",
                        lane=lane_name,
                        status="active",
                        subtitle=(model or role or "active"),
                        meta={
                            "request_id": request_id,
                            "project": project,
                            "lane": lane_name,
                            "persona": persona_label,
                            "role": role,
                            "model": model,
                            "directive": directive,
                            "status": "active",
                        },
                    )
                    add_edge(job_node_id, agent_node_id, label="active")
                    active_count += 1
            return active_count

        foraging_active_agents = _add_job_group(foraging_jobs, lane_name="foraging", lane_node_id=lane_foraging_id)
        building_active_agents = _add_job_group(building_jobs, lane_name="building", lane_node_id=lane_building_id)

        kind_order = {"root": 0, "lane": 1, "job": 2, "agent": 3}
        nodes = sorted(
            nodes_by_id.values(),
            key=lambda node: (
                kind_order.get(str(node.get("kind", "")), 99),
                str(node.get("lane", "")),
                str(node.get("label", "")),
                str(node.get("id", "")),
            ),
        )

        summary = {
            "active_jobs": len(foraging_jobs) + len(building_jobs),
            "foraging_jobs": len(foraging_jobs),
            "building_jobs": len(building_jobs),
            "active_agents": foraging_active_agents + building_active_agents,
            "foraging_active_agents": foraging_active_agents,
            "building_active_agents": building_active_agents,
        }

        return {
            "generated_at": _now_iso(),
            "summary": summary,
            "nodes": nodes,
            "edges": edges,
        }, 200
