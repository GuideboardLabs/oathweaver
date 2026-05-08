"""Lesson and reflection management — thin service wrappers with bus emission."""

from __future__ import annotations

from typing import Any


def lessons_text(learning_engine, lane: str | None = None, limit: int = 10) -> str:
    return learning_engine.lessons_text(lane=lane, limit=limit)


def lesson_guidance_text(learning_engine, lane: str | None = None, limit: int = 5) -> str:
    lane_key = (lane or "project").strip().lower()
    guidance = learning_engine.guidance_for_lane(lane_key, limit=limit)
    if not guidance:
        return f"No guidance learned yet for lane '{lane_key}'."
    return guidance


def lesson_reinforce(learning_engine, bus, lesson_id: str, direction: str, note: str = "") -> str:
    try:
        row = learning_engine.reinforce(lesson_id, direction=direction, note=note)
    except ValueError as exc:
        return str(exc)
    if row is None:
        return f"Lesson id not found: {lesson_id}"
    bus.emit(
        "orchestrator",
        "learning_reinforced",
        {"lesson_id": lesson_id, "direction": direction, "score": row.get("score", 0)},
    )
    return (
        f"Lesson updated: {lesson_id} | direction={direction} | "
        f"new_score={float(row.get('score', 0.0)):.2f}"
    )


def lesson_expire(learning_engine, bus, lesson_id: str) -> str:
    row = learning_engine.expire_lesson(lesson_id.strip())
    if row is None:
        return f"Lesson id not found: {lesson_id}"
    bus.emit("orchestrator", "lesson_expired", {"lesson_id": lesson_id})
    return f"Lesson expired: {lesson_id} | summary={row.get('summary', '')[:80]}"


def reflection_open_text(reflection_engine, limit: int = 10) -> str:
    return reflection_engine.open_text(limit=limit)


def reflection_history_text(reflection_engine, limit: int = 10) -> str:
    return reflection_engine.history_text(limit=limit)


def reflection_answer(reflection_engine, bus, cycle_id: str, answer: str) -> str:
    try:
        cycle = reflection_engine.answer(cycle_id=cycle_id, answer_text=answer)
    except ValueError as exc:
        return str(exc)
    if cycle is None:
        return f"Reflection id not found or already closed: {cycle_id}"
    bus.emit(
        "orchestrator",
        "reflection_answered",
        {"id": cycle_id, "lane": cycle.get("lane", ""), "project": cycle.get("project", "")},
    )
    lesson_ids = cycle.get("answer_lesson_ids", [])
    learning_status = str(cycle.get("learning_status", "")).strip().lower()
    preview = ", ".join(lesson_ids[:6]) if lesson_ids else "none"
    learning_note = ""
    if learning_status in {"queued", "running"}:
        learning_note = "\nLesson extraction is queued and will finish in the background."
    elif learning_status == "failed":
        learning_note = "\nLesson extraction hit a background error; reflection was still saved."
    return (
        f"Reflection answered and closed: {cycle_id}\n"
        f"New lesson IDs from your answer: {preview}"
        f"{learning_note}"
    )


def learn_outbox(learning_engine, bus, target: str, lane_hint: str | None = None, limit: int = 5) -> str:
    try:
        result = learning_engine.ingest_outbox(target, lane_hint=lane_hint, limit=limit)
    except ValueError as exc:
        return str(exc)
    bus.emit(
        "orchestrator",
        "learning_ingested_outbox",
        {
            "source": result.get("source", ""),
            "processed_files": result.get("processed_files", 0),
            "learned_lessons": result.get("learned_lessons", 0),
        },
    )
    ids = result.get("lesson_ids", [])
    preview = ", ".join(ids[:8]) if ids else "none"
    return (
        f"{result.get('message', 'Ingestion completed.')}\n"
        f"Lesson IDs: {preview}\n"
        "Use /lessons [lane] [limit] and /lesson-reinforce <id> <up|down> [note]."
    )


def learn_outbox_one(
    learning_engine, bus, target: str, thread_id: str, lane_hint: str | None = None
) -> dict[str, Any]:
    try:
        result = learning_engine.ingest_outbox_thread(target, request_id=thread_id, lane_hint=lane_hint)
    except ValueError as exc:
        return {
            "ok": False,
            "source": target,
            "thread_id": thread_id,
            "processed_files": 0,
            "learned_lessons": 0,
            "lesson_ids": [],
            "message": str(exc),
        }
    bus.emit(
        "orchestrator",
        "learning_ingested_outbox_one",
        {
            "source": result.get("source", ""),
            "thread_id": result.get("thread_id", ""),
            "processed_files": result.get("processed_files", 0),
            "learned_lessons": result.get("learned_lessons", 0),
        },
    )
    result["ok"] = int(result.get("processed_files", 0)) > 0
    return result
