from __future__ import annotations

import hashlib
import json
import uuid
from pathlib import Path
from typing import Any
from orchestrator.services.policy import _resolve_domain

_LANGGRAPH_AVAILABLE = False
try:  # pragma: no cover - optional dependency
    from langgraph.graph import END, StateGraph
    from langgraph.checkpoint.sqlite import SqliteSaver

    _LANGGRAPH_AVAILABLE = True
except Exception:  # pragma: no cover - graceful fallback when langgraph is absent
    END = None
    StateGraph = None
    SqliteSaver = None


def _hash_text(text: str) -> str:
    return hashlib.sha256(str(text or "").encode("utf-8")).hexdigest()[:16]


def _checkpoint_path(repo_root: Path) -> Path:
    path = Path(repo_root) / "Runtime" / "state" / "turn_checkpoints.sqlite"
    path.parent.mkdir(parents=True, exist_ok=True)
    return path


def _graph_version_hash() -> str:
    shape = {
        "nodes": [
            "ingest",
            "prompt_digest",
            "intent_confirm",
            "lane_route",
            "context_gate",
            "lane_execute",
            "compose",
            "persist",
        ],
        "edges": [
            ["ingest", "prompt_digest"],
            ["prompt_digest", "intent_confirm"],
            ["intent_confirm", "lane_route"],
            ["lane_route", "context_gate"],
            ["context_gate", "lane_execute"],
            ["lane_execute", "compose"],
            ["compose", "persist"],
            ["persist", "END"],
        ],
    }
    return hashlib.sha256(json.dumps(shape, sort_keys=True).encode("utf-8")).hexdigest()[:16]


def _assert_serializable(state_update: dict[str, Any], node_name: str) -> dict[str, Any]:
    try:
        json.dumps(state_update, ensure_ascii=True)
    except Exception as exc:
        raise TypeError(f"TurnGraph node '{node_name}' emitted non-serializable state: {exc}") from exc
    return state_update


def _run_fallback(
    orchestrator: Any,
    *,
    text: str,
    history: list[dict[str, str]] | None,
    cancel_checker=None,
    progress_callback=None,
) -> dict[str, Any]:
    reply = orchestrator.conversation_reply(
        text,
        history=history,
        project=orchestrator.project_slug,
        cancel_checker=cancel_checker,
        progress_callback=progress_callback,
    )
    return {
        "reply": reply,
        "state": {
            "text": text,
            "history": list(history or []),
            "lane": "conversation",
            "intent": "chat",
            "prompt_digest": _hash_text(text),
            "composed_answer": reply,
            "perf_trace": {"pipeline": "fallback"},
            "graph_version_hash": _graph_version_hash(),
        },
        "graph_used": False,
    }


def _select_lane(orchestrator: Any, text: str, history: list[dict[str, str]] | None = None) -> str:
    try:
        from shared_tools.model_routing import lane_model_config

        recent_context = ""
        rows = history if isinstance(history, list) else []
        if rows:
            clip = []
            for row in rows[-6:]:
                role = str((row or {}).get("role", "")).strip().lower()
                content = str((row or {}).get("content", "")).strip()
                if role in {"user", "assistant"} and content:
                    clip.append(f"{role.upper()}: {content[:120]}")
            if clip:
                recent_context = "Recent conversation:\n" + "\n".join(clip)

        plan = orchestrator.turn_planner.plan(
            text,
            project=orchestrator.project_slug,
            client=orchestrator.ollama,
            model_cfg=lane_model_config(orchestrator.repo_root, "orchestrator_reasoning"),
            recent_context=recent_context,
        )
        lane = str(plan.lane or "").strip().lower() or "conversation"
        if getattr(plan, "lane_override", None) and lane in {"research", "project", "personal"}:
            lane = str(plan.lane_override).strip().lower() or lane
        return lane
    except Exception:
        return "conversation"


def compile_chat_turn_graph(
    orchestrator: Any,
    *,
    cancel_checker=None,
    progress_callback=None,
    with_checkpointer: bool = True,
):
    if not _LANGGRAPH_AVAILABLE:
        return None, None, _graph_version_hash()

    def ingest(state: dict[str, Any]) -> dict[str, Any]:
        return _assert_serializable(
            {
                "text": str(state.get("text", "")).strip(),
                "history": list(state.get("history") or []),
                "lane": "conversation",
            },
            "ingest",
        )

    def prompt_digest(state: dict[str, Any]) -> dict[str, Any]:
        text_value = str(state.get("text", "")).strip()
        return _assert_serializable(
            {
                "prompt_digest": _hash_text(text_value),
                "perf_trace": {"prompt_chars": len(text_value)},
                "graph_version_hash": _graph_version_hash(),
            },
            "prompt_digest",
        )

    def intent_confirm(state: dict[str, Any]) -> dict[str, Any]:
        text_value = str(state.get("text", "")).strip()
        history_rows = list(state.get("history") or [])
        gate_decision: dict[str, Any] = {}
        intent = "chat"
        try:
            from orchestrator.services.intent_confirmer import confirm_make_intent

            gate_decision = confirm_make_intent(
                text_value,
                Path(orchestrator.repo_root),
                ui_mode="talk",
                make_type="",
            )
            intent = str(gate_decision.get("intent", "chat")).strip().lower() or "chat"
        except Exception as exc:
            gate_decision = {"intent": "chat", "confidence": 0.0, "reason": f"intent gate failed: {exc}"}
            intent = "chat"

        return _assert_serializable(
            {
                "intent": intent,
                "gate_decision": gate_decision,
                "lane_hint": _select_lane(orchestrator, text_value, history_rows),
            },
            "intent_confirm",
        )

    def lane_route(state: dict[str, Any]) -> dict[str, Any]:
        intent = str(state.get("intent", "chat")).strip().lower()
        lane_hint = str(state.get("lane_hint", "conversation")).strip().lower() or "conversation"
        lane = lane_hint
        gate_decision = state.get("gate_decision", {}) if isinstance(state.get("gate_decision", {}), dict) else {}
        make_type = str(gate_decision.get("suggested_type", "")).strip().lower()
        domain = _resolve_domain(make_type, str(state.get("domain", "general_research")).strip())
        if intent == "forage":
            lane = "research"
        elif intent == "make":
            lane = "ui"
        if lane in {"project", "personal"}:
            lane = "conversation"
        return _assert_serializable({"lane": lane, "domain": domain, "make_type": make_type}, "lane_route")

    def context_gate(state: dict[str, Any]) -> dict[str, Any]:
        text_value = str(state.get("text", "")).strip()
        _, _, _ = orchestrator._context_bundle_for_query(  # pylint: disable=protected-access
            text_value,
            household_chars=900,
        )
        return _assert_serializable(
            {
                "foraging_plan": {"eligible": False},
                "context_gate": {"personal_context": False},
            },
            "context_gate",
        )

    def lane_execute(state: dict[str, Any]) -> dict[str, Any]:
        lane = str(state.get("lane", "conversation")).strip().lower() or "conversation"
        if lane != "conversation":
            return _assert_serializable(
                {
                    "routing_redirect": {
                        "lane": lane,
                        "reason": "turn_graph_chat_only",
                    },
                    "agent_findings": [],
                    "composed_answer": "",
                },
                "lane_execute",
            )

        reply = orchestrator.conversation_reply(
            str(state.get("text", "")).strip(),
            history=list(state.get("history") or []),
            project=orchestrator.project_slug,
            cancel_checker=cancel_checker,
            progress_callback=progress_callback,
        )
        return _assert_serializable({"agent_findings": [], "composed_answer": reply}, "lane_execute")

    def compose(state: dict[str, Any]) -> dict[str, Any]:
        return _assert_serializable({"composed_answer": str(state.get("composed_answer", "")).strip()}, "compose")

    def persist(state: dict[str, Any]) -> dict[str, Any]:
        return _assert_serializable({"final_reply": str(state.get("composed_answer", "")).strip()}, "persist")

    builder = StateGraph(dict)
    builder.add_node("ingest", ingest)
    builder.add_node("prompt_digest", prompt_digest)
    builder.add_node("intent_confirm", intent_confirm)
    builder.add_node("lane_route", lane_route)
    builder.add_node("context_gate", context_gate)
    builder.add_node("lane_execute", lane_execute)
    builder.add_node("compose", compose)
    builder.add_node("persist", persist)
    builder.set_entry_point("ingest")
    builder.add_edge("ingest", "prompt_digest")
    builder.add_edge("prompt_digest", "intent_confirm")
    builder.add_edge("intent_confirm", "lane_route")
    builder.add_edge("lane_route", "context_gate")
    builder.add_edge("context_gate", "lane_execute")
    builder.add_edge("lane_execute", "compose")
    builder.add_edge("compose", "persist")
    builder.add_edge("persist", END)

    checkpoint = _checkpoint_path(Path(orchestrator.repo_root))
    checkpointer = None
    if with_checkpointer:
        try:  # pragma: no cover - optional dependency path
            checkpointer = SqliteSaver.from_conn_string(str(checkpoint))
        except Exception:
            checkpointer = None

    graph = builder.compile(checkpointer=checkpointer)
    return graph, checkpoint, _graph_version_hash()


def invoke_chat_turn_graph(
    orchestrator: Any,
    *,
    text: str,
    history: list[dict[str, str]] | None = None,
    cancel_checker=None,
    progress_callback=None,
    thread_id: str = "",
) -> dict[str, Any]:
    """Run chat lane through a LangGraph state pipeline when available."""
    if not _LANGGRAPH_AVAILABLE:
        return _run_fallback(
            orchestrator,
            text=text,
            history=history,
            cancel_checker=cancel_checker,
            progress_callback=progress_callback,
        )

    graph, checkpoint, version_hash = compile_chat_turn_graph(
        orchestrator,
        cancel_checker=cancel_checker,
        progress_callback=progress_callback,
        with_checkpointer=True,
    )
    if graph is None:
        return _run_fallback(
            orchestrator,
            text=text,
            history=history,
            cancel_checker=cancel_checker,
            progress_callback=progress_callback,
        )

    input_state = {
        "text": str(text or "").strip(),
        "history": list(history or []),
        "lane": "conversation",
        "intent": "chat",
        "agent_findings": [],
        "perf_trace": {},
    }
    stable_thread = str(thread_id or "").strip() or f"thread_{uuid.uuid4().hex[:16]}"
    result_state = graph.invoke(input_state, config={"configurable": {"thread_id": stable_thread}})

    lane = str(result_state.get("lane", "conversation")).strip().lower()
    reply = str(result_state.get("final_reply", "")).strip() or str(result_state.get("composed_answer", "")).strip()
    if lane != "conversation" or not reply:
        fallback = _run_fallback(
            orchestrator,
            text=text,
            history=history,
            cancel_checker=cancel_checker,
            progress_callback=progress_callback,
        )
        fallback_state = dict(fallback.get("state") or {})
        fallback_state["graph_attempted"] = True
        fallback_state["graph_lane"] = lane
        fallback_state["graph_version_hash"] = version_hash
        fallback_state["thread_id"] = stable_thread
        fallback["state"] = fallback_state
        return fallback

    result_state["thread_id"] = stable_thread
    result_state["turn_id"] = stable_thread
    result_state["checkpoint_path"] = str(checkpoint) if checkpoint else ""
    result_state["graph_version_hash"] = version_hash
    return {"reply": reply, "state": result_state, "graph_used": True}


__all__ = [
    "compile_chat_turn_graph",
    "invoke_chat_turn_graph",
]
