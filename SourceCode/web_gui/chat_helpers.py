"""Helpers and constants for the chat blueprint, extracted from app.py to avoid circular imports."""
from __future__ import annotations

import logging
import os
from pathlib import Path
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from shared_tools.conversation_store import ConversationStore
    from orchestrator.main import OathweaverOrchestrator

LOGGER = logging.getLogger(__name__)

GENERAL_PROJECT = "general"
DEFAULT_PROJECT = GENERAL_PROJECT

ATTACHMENT_MAX_IMAGES = 4
ATTACHMENT_MAX_IMAGE_BYTES = 8 * 1024 * 1024
ATTACHMENT_MAX_DOC_BYTES = 20 * 1024 * 1024
ALLOWED_IMAGE_MIME = {"image/png", "image/jpeg", "image/webp", "image/gif", "image/bmp"}
ALLOWED_IMAGE_EXT = {".png", ".jpg", ".jpeg", ".webp", ".gif", ".bmp"}
ALLOWED_DOC_MIME = {
    "application/pdf",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "application/msword",
    "text/plain",
    "text/markdown",
    "text/csv",
}
ALLOWED_DOC_EXT = {".pdf", ".docx", ".doc", ".txt", ".md", ".csv"}
VISION_MODEL_HINTS = ("llama3.2-vision", "llava", "bakllava", "moondream", "minicpm-v", "qwen2.5vl", "qwen-vl")
VISION_MODEL_PRIORITY = ("moondream", "llava:7b", "llava", "bakllava", "llama3.2-vision", "minicpm-v", "qwen2.5vl", "qwen-vl")


def bg_summarize(conversation_id: str, store: ConversationStore, root: Path) -> None:
    try:
        from shared_tools.model_routing import lane_model_config
        from shared_tools.inference_router import InferenceRouter
        conv = store.get(conversation_id)
        if not conv:
            return
        messages = conv.get("messages", [])
        if len(messages) < 4:
            return
        recent = messages[-12:]
        lines = []
        for m in recent:
            role = str(m.get("role", "")).capitalize()
            content = str(m.get("content", "")).strip()[:400]
            lines.append(f"{role}: {content}")
        transcript = "\n".join(lines)
        cfg = lane_model_config(root, "orchestrator_reasoning")
        model = str(cfg.get("model", "")).strip()
        if not model:
            return
        client = InferenceRouter(root)
        result = client.chat(
            model=model,
            system_prompt="Summarize this conversation in 2-3 sentences. Focus on what was asked and what was learned.",
            user_prompt=transcript,
            temperature=0.2,
            num_ctx=2048,
            timeout=20,
            retry_attempts=1,
        )
        if result:
            store.update_summary(conversation_id, result)
    except Exception:
        LOGGER.exception("Background conversation summary failed for %s.", conversation_id)


def bg_retitle(conversation_id: str, store: ConversationStore, root: Path) -> None:
    try:
        from shared_tools.model_routing import lane_model_config
        from shared_tools.inference_router import InferenceRouter
        conv = store.get(conversation_id)
        if not conv:
            return
        if bool(conv.get("title_manually_set", False)):
            return
        messages = conv.get("messages", [])[:4]
        lines = []
        for m in messages:
            role = str(m.get("role", "")).capitalize()
            content = str(m.get("content", "")).strip()[:300]
            lines.append(f"{role}: {content}")
        transcript = "\n".join(lines)
        cfg = lane_model_config(root, "orchestrator_reasoning")
        model = str(cfg.get("model", "")).strip()
        if not model:
            return
        client = InferenceRouter(root)
        result = client.chat(
            model=model,
            system_prompt="Generate a concise 5-8 word title for this conversation. Return ONLY the title, no quotes.",
            user_prompt=transcript,
            temperature=0.2,
            num_ctx=512,
            timeout=10,
            retry_attempts=1,
        )
        if result:
            new_title = result.strip()[:64]
            store.rename(conversation_id, new_title, manual=False)
            updated = store.get(conversation_id)
            if updated and str(updated.get("topic_id", "")).strip() not in ("", "general"):
                project_slug = str(updated.get("project", "")).strip()
                if project_slug and project_slug != "general":
                    new_path = store._generate_path(project_slug, new_title)
                    store.set_path(conversation_id, new_path)
    except Exception:
        LOGGER.exception("Background conversation retitle failed for %s.", conversation_id)


def vision_model_candidates(orch: OathweaverOrchestrator) -> list[str]:
    preferred = str(os.environ.get("OATHWEAVER_VISION_MODEL", "")).strip()
    try:
        local_models = [str(x).strip() for x in orch.ollama.list_local_models() if str(x).strip()]
    except Exception:
        local_models = []
    vision_models = [m for m in local_models if any(hint in m.lower() for hint in VISION_MODEL_HINTS)]

    def _rank(name: str) -> tuple[int, str]:
        low = name.lower()
        for idx, hint in enumerate(VISION_MODEL_PRIORITY):
            if hint in low:
                return idx, low
        return len(VISION_MODEL_PRIORITY), low

    ordered = sorted(vision_models, key=_rank)
    out: list[str] = []
    if preferred:
        out.append(preferred)
    for model in ordered:
        if model not in out:
            out.append(model)
    return out


def handle_command(
    orch: OathweaverOrchestrator,
    text: str,
    *,
    command_history: list[dict[str, str]] | None = None,
    project_mode: dict[str, Any] | None = None,
) -> str:
    from web_gui.utils.request_utils import parse_optional_int as _parse_optional_int
    if text == "/status":
        return orch.status_text()
    if text.startswith("/activity"):
        limit = _parse_optional_int(text.split(maxsplit=1)[1] if " " in text else None, default=20)
        return orch.activity_text(limit=limit)
    if text.startswith("/lanes"):
        window = _parse_optional_int(text.split(maxsplit=1)[1] if " " in text else None, default=200)
        return orch.lanes_text(window=window)
    if text.startswith("/artifacts"):
        limit = _parse_optional_int(text.split(maxsplit=1)[1] if " " in text else None, default=20)
        return orch.artifacts_text(limit=limit)
    if text == "/dashboard":
        return "\n\n".join([orch.status_text(), orch.lanes_text(window=200), orch.artifacts_text(limit=20)])
    if text == "/pending":
        return orch.pending_approvals_text()
    if text.startswith("/approve "):
        return orch.decide_approval(text[len("/approve "):].strip(), True)
    if text.startswith("/reject "):
        return orch.decide_approval(text[len("/reject "):].strip(), False)
    if text == "/models":
        return orch.models_text()
    if text == "/local-models":
        return orch.local_models_text()
    if text == "/reload-models":
        return orch.reload_models()
    if text.startswith("/web-mode"):
        parts = text.split()
        if len(parts) == 1:
            return orch.web_mode_text()
        return orch.set_web_mode(parts[1].strip())
    if text.startswith("/external-mode"):
        parts = text.split()
        if len(parts) == 1:
            return orch.external_tools_mode_text()
        return orch.set_external_tools_mode(parts[1].strip())
    if text.startswith("/web-provider"):
        parts = text.split()
        if len(parts) == 1:
            return orch.web_provider_text()
        return orch.set_web_provider(parts[1].strip())
    if text.startswith("/web-sources"):
        parts = text.split()
        limit = int(parts[1]) if len(parts) > 1 and parts[1].isdigit() else 10
        return orch.web_sources_text(limit=limit)
    if text == "/project-facts":
        return orch.project_facts_text()
    if text == "/project-facts-clear":
        return orch.clear_project_facts()
    if text == "/project-facts-refresh":
        try:
            rows = command_history or []
            if not rows:
                return (
                    "Project fact refresh skipped: no user history was available to parse.\n"
                    "Send a few normal messages first, then run /project-facts-refresh."
                )
            return orch.refresh_project_facts(history=rows, reset=True)
        except Exception as exc:
            return f"Project fact refresh failed: {exc.__class__.__name__}: {exc}"
    if text == "/improve-status":
        return orch.improvement_status_text()
    if text == "/improve-now":
        try:
            return orch.improvement_run_now(history=command_history or [])
        except Exception as exc:
            return f"Continuous improvement refresh failed: {exc.__class__.__name__}: {exc}"
    if text == "/handoff-pending":
        return orch.handoff_pending_text()
    if text.startswith("/handoff-approve "):
        parts = text.split(maxsplit=2)
        request_id = parts[1].strip() if len(parts) > 1 else ""
        reason = parts[2].strip() if len(parts) > 2 else ""
        return orch.approve_handoff(request_id=request_id, reason=reason)
    if text.startswith("/handoff-deny "):
        parts = text.split(maxsplit=2)
        if len(parts) < 3:
            return "Usage: /handoff-deny <id> <reason>"
        return orch.deny_handoff(request_id=parts[1].strip(), reason=parts[2].strip())
    if text.startswith("/handoff-inbox"):
        parts = text.split(maxsplit=1)
        target = parts[1].strip() if len(parts) > 1 else None
        return orch.handoff_inbox_text(target=target)
    if text.startswith("/handoff-outbox"):
        parts = text.split()
        target = parts[1].strip().lower() if len(parts) > 1 and not parts[1].isdigit() else None
        number_arg = next((p for p in parts[1:] if p.isdigit()), None)
        limit = int(number_arg) if number_arg else 20
        return orch.handoff_outbox_text(target=target, limit=limit)
    if text == "/handoff-sync":
        return orch.handoff_sync()
    if text.startswith("/handoff-monitor"):
        parts = text.split()
        limit = int(parts[1]) if len(parts) > 1 and parts[1].isdigit() else 50
        return orch.handoff_monitor_text(limit=limit)
    if text.startswith("/handoff "):
        parts = text.split(maxsplit=2)
        if len(parts) < 3:
            return "Usage: /handoff <codex> <request text>"
        return orch.create_handoff(target=parts[1].strip(), request_text=parts[2].strip())
    if text.startswith("/learn-outbox "):
        parts = text.split()
        if len(parts) < 2:
            return "Usage: /learn-outbox <codex> [lane] [n]"
        target = parts[1].strip().lower()
        lane_hint = None
        limit = 5
        for token in parts[2:]:
            if token.isdigit():
                limit = int(token)
            else:
                lane_hint = token.strip().lower()
        return orch.learn_outbox(target=target, lane_hint=lane_hint, limit=limit)
    if text.startswith("/learn-outbox-one "):
        parts = text.split()
        if len(parts) < 3:
            return "Usage: /learn-outbox-one <codex> <thread_id> [lane]"
        target = parts[1].strip().lower()
        thread_id = parts[2].strip()
        lane_hint = parts[3].strip().lower() if len(parts) > 3 else None
        result = orch.learn_outbox_one(target=target, thread_id=thread_id, lane_hint=lane_hint)
        ids = ", ".join(result.get("lesson_ids", [])[:8]) or "none"
        return f"{result.get('message', '')}\nLesson IDs: {ids}"
    if text.startswith("/lessons"):
        parts = text.split()
        lane = None
        limit = 10
        for token in parts[1:]:
            if token.isdigit():
                limit = int(token)
            else:
                lane = token.strip().lower()
        return orch.lessons_text(lane=lane, limit=limit)
    if text.startswith("/lesson-guidance"):
        parts = text.split()
        lane = None
        limit = 5
        for token in parts[1:]:
            if token.isdigit():
                limit = int(token)
            else:
                lane = token.strip().lower()
        return orch.lesson_guidance_text(lane=lane, limit=limit)
    if text.startswith("/lesson-reinforce "):
        parts = text.split(maxsplit=3)
        if len(parts) < 3:
            return "Usage: /lesson-reinforce <id> <up|down> [note]"
        lesson_id = parts[1].strip()
        direction = parts[2].strip().lower()
        note = parts[3].strip() if len(parts) > 3 else ""
        return orch.lesson_reinforce(lesson_id=lesson_id, direction=direction, note=note)
    if text.startswith("/reflect-open"):
        parts = text.split()
        limit = int(parts[1]) if len(parts) > 1 and parts[1].isdigit() else 10
        return orch.reflection_open_text(limit=limit)
    if text.startswith("/reflect-history"):
        parts = text.split()
        limit = int(parts[1]) if len(parts) > 1 and parts[1].isdigit() else 10
        return orch.reflection_history_text(limit=limit)
    if text.startswith("/reflect-answer "):
        parts = text.split(maxsplit=2)
        if len(parts) < 3:
            return "Usage: /reflect-answer <id> <answer>"
        cycle_id = parts[1].strip()
        answer = parts[2].strip()
        return orch.reflection_answer(cycle_id=cycle_id, answer=answer)
    if text.startswith("/pending-actions"):
        parts = text.split()
        limit = int(parts[1]) if len(parts) > 1 and parts[1].isdigit() else 20
        return orch.pending_actions_text(limit=limit)
    if text.startswith("/action-ignore "):
        parts = text.split(maxsplit=2)
        if len(parts) < 2:
            return "Usage: /action-ignore <id> [reason]"
        action_id = parts[1].strip()
        reason = parts[2].strip() if len(parts) > 2 else ""
        return orch.ignore_pending_action(action_id=action_id, reason=reason)
    if text.startswith("/action-codex "):
        parts = text.split(maxsplit=2)
        if len(parts) < 2:
            return "Usage: /action-codex <id> [note]"
        action_id = parts[1].strip()
        note = parts[2].strip() if len(parts) > 2 else ""
        return orch.send_pending_action_to_codex(action_id=action_id, note=note)
    if text.startswith("/action-answer "):
        parts = text.split(maxsplit=2)
        if len(parts) < 3:
            return "Usage: /action-answer <id> <answer>"
        action_id = parts[1].strip()
        answer = parts[2].strip()
        return orch.answer_pending_action(action_id=action_id, answer=answer)
    if text.startswith("/workspace-tree"):
        parts = text.split(maxsplit=2)
        rel_path = parts[1].strip() if len(parts) > 1 and not parts[1].isdigit() else "."
        depth = int(parts[2]) if len(parts) > 2 and parts[2].isdigit() else 2
        return orch.workspace_tree_text(rel_path=rel_path, max_depth=depth)
    if text.startswith("/workspace-read "):
        return orch.workspace_read_text(text[len("/workspace-read "):].strip())
    if text.startswith("/workspace-search "):
        body = text[len("/workspace-search "):].strip()
        if not body:
            return "Usage: /workspace-search <query> [ | <glob>]"
        if " | " in body:
            query, rel_glob = body.split(" | ", 1)
        else:
            query, rel_glob = body, "*"
        return orch.workspace_search_text(query=query.strip(), rel_glob=rel_glob.strip() or "*")
    if text.startswith("/workspace-patch "):
        body = text[len("/workspace-patch "):].strip()
        if " | " not in body:
            return "Usage: /workspace-patch <relative_path> | <instruction>"
        rel_path, instruction = body.split(" | ", 1)
        return orch.workspace_patch_text(rel_path=rel_path.strip(), instruction=instruction.strip())
    if text.startswith("/workspace-patch-batch "):
        body = text[len("/workspace-patch-batch "):].strip()
        if " | " not in body:
            return "Usage: /workspace-patch-batch <path1, path2, ...> | <instruction>"
        paths_part, instruction = body.split(" | ", 1)
        rel_paths = [part.strip() for part in paths_part.split(",") if part.strip()]
        return orch.workspace_patch_batch_text(rel_paths=rel_paths, instruction=instruction.strip())
    if text.startswith("/workspace-patches"):
        parts = text.split()
        limit = int(parts[1]) if len(parts) > 1 and parts[1].isdigit() else 20
        return orch.workspace_pending_patches_text(limit=limit)
    if text.startswith("/workspace-apply "):
        return orch.approve_action_proposal(text[len("/workspace-apply "):].strip())
    if text.startswith("/workspace-reject "):
        proposal_id = text[len("/workspace-reject "):].strip()
        ok = orch.approval_gate.decide(proposal_id, approved=False)
        return f"Patch proposal {'rejected' if ok else 'not found'}: {proposal_id}"
    if text.startswith("/project "):
        return orch.set_project(text[len("/project "):].strip())
    if text.startswith("/ui "):
        ui_text = text[len("/ui "):].strip()
        ui_mode = {"mode": "make", "target": "app", "topic_type": "technical"}
        return orch.handle_message(ui_text, history=command_history, project_mode=ui_mode)
    if text.startswith("/make "):
        make_text = text[len("/make "):].strip()
        make_mode = {"mode": "make", "target": "auto", "topic_type": "general"}
        return orch.handle_message(make_text, history=command_history, project_mode=make_mode)
    if text.startswith("/project-mode"):
        parts = text.split()
        if len(parts) == 1:
            snap = project_mode or orch.project_mode_snapshot()
            return (
                f"Project mode: {snap.get('mode', 'discovery')} | "
                f"topic_type={snap.get('topic_type', 'general')} | target={snap.get('target', 'auto')}"
            )
        mode = parts[1].strip().lower() if len(parts) > 1 else None
        target = parts[2].strip().lower() if len(parts) > 2 else None
        row = orch.set_project_mode(mode=mode, target=target)
        return (
            f"Project mode updated: {row.get('mode', 'discovery')} | "
            f"topic_type={row.get('topic_type', 'general')} | target={row.get('target', 'auto')}"
        )
    if text.startswith("/replay"):
        parts = text.split(maxsplit=1)
        args = parts[1].strip() if len(parts) > 1 else ""
        if not args:
            return "Usage: /replay <turn_id> [from=<node>] [mutate={...json...}]"
        mutate_json = ""
        mutate_pos = args.find("mutate=")
        if mutate_pos >= 0:
            mutate_json = args[mutate_pos + len("mutate="):].strip()
            args = args[:mutate_pos].strip()
        turn_id = args.split()[0] if args else ""
        from_node = ""
        for token in args.split()[1:]:
            if token.startswith("from="):
                from_node = token[len("from="):].strip()
        return orch.replay_turn_text(turn_id, from_node=from_node, mutate_json=mutate_json)
    if text == "/regression":
        return orch.regression_text()
    if text.startswith("/talk "):
        return orch.conversation_reply(text[len("/talk "):].strip())
    return (
        "Unknown slash command. Try /status, /models, /local-models, /pending, "
        "/approve <id>, /reject <id>, /handoff <target> <text>, /handoff-pending, "
        "/web-mode [off|ask|auto], /web-provider [auto|searxng|duckduckgo_html|duckduckgo_api], /web-sources [n], "
        "/external-mode [off|ask|auto], "
        "/project-facts, /project-facts-clear, /project-facts-refresh, "
        "/improve-status, /improve-now, "
        "/handoff-approve <id>, /handoff-deny <id> <reason>, /handoff-inbox [target], /handoff-sync, /handoff-monitor [n], "
        "/handoff-outbox [target] [n], /learn-outbox <target> [lane] [n], /lessons [lane] [n], "
        "/learn-outbox-one <target> <thread_id> [lane], "
        "/lesson-guidance [lane] [n], /lesson-reinforce <id> <up|down> [note], "
        "/reflect-open [n], /reflect-answer <id> <answer>, /reflect-history [n], "
        "/pending-actions [n], /action-ignore <id> [reason], /action-codex <id> [note], /action-answer <id> <answer>, "
        "/workspace-tree [path] [depth], /workspace-read <path>, /workspace-search <query> [glob], "
        "/workspace-patch <path> | <instruction>, /workspace-patch-batch <path1, path2> | <instruction>, "
        "/workspace-patches [n], /workspace-apply <id>, /workspace-reject <id>, "
        "/project <slug>, /project-mode [mode] [stage] [target], /make <request>, "
        "/replay <turn_id> [from=<node>] [mutate={...json...}], /regression, /talk <text>."
    )
