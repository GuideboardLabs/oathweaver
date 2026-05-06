"""Status aggregation — builds the Oathweaver status dashboard text."""

from __future__ import annotations


def build_status_text(
    *,
    project_slug: str,
    activity_store,
    approval_gate,
    handoff_queue,
    learning_engine,
    reflection_engine,
    web_engine,
    external_tools_settings,
    external_request_store,
    project_memory,
    pipeline_store,
    improvement_engine,
) -> str:
    handoff_queue.sync_outbox_placeholders()
    rows = activity_store.rows()
    pending = approval_gate.list_pending()
    pending_handoffs = handoff_queue.count_pending()
    learned_lessons = learning_engine.count_lessons()
    open_reflections = reflection_engine.count_open()
    open_web = len(web_engine.list_pending(limit=500))
    web_mode = web_engine.get_mode()
    external_mode = external_tools_settings.get_mode()
    open_external = 0
    if external_mode != "off":
        try:
            open_external = len(external_request_store.list_open(limit=500))
        except Exception:
            open_external = 0
    fact_count = len(project_memory.get_facts(project_slug))
    pipeline = pipeline_store.get(project_slug)
    improvement = improvement_engine.status_snapshot(project_slug)
    project_improve = improvement.get("project", {})
    monitored = handoff_queue.monitor_threads(limit=500)
    waiting_output = len([x for x in monitored if str(x.get("status", "")) == "waiting_output"])
    ready_for_ingest = len([x for x in monitored if str(x.get("status", "")) == "ready_for_ingest"])
    last_event = rows[-1].get("event") if rows else "none"
    return "\n".join([
        "Oathweaver status:",
        f"- active_project: {project_slug}",
        f"- total_events: {len(rows)}",
        f"- pending_approvals: {len(pending)}",
        f"- pending_handoffs: {pending_handoffs}",
        f"- handoff_waiting_output: {waiting_output}",
        f"- handoff_ready_for_ingest: {ready_for_ingest}",
        f"- learned_lessons: {learned_lessons}",
        f"- open_reflections: {open_reflections}",
        f"- web_mode: {web_mode}",
        f"- open_web_requests: {open_web}",
        "- cloud_mode: off (disabled)",
        "- open_cloud_requests: 0",
        f"- external_tools_mode: {external_mode}",
        f"- open_external_requests: {open_external}",
        f"- known_project_facts: {fact_count}",
        (
            f"- project_mode: {pipeline.get('mode', 'discovery')} | "
            f"topic_type={pipeline.get('topic_type', 'general')} | target={pipeline.get('target', 'auto')}"
        ),
        f"- continuous_improvement: {'on' if improvement.get('enabled', True) else 'off'}",
        f"- project_quality_avg: {float(project_improve.get('avg_quality', 0.0)):.2f}",
        f"- project_turns_seen: {int(project_improve.get('turns', 0))}",
        f"- last_event: {last_event}",
    ])
