"""Conversation history builders — format raw message dicts into LLM history lists."""

from __future__ import annotations

from typing import Any


def extract_talk_text(raw: str) -> str | None:
    """Return the text after '/talk' if the message is a talk-mode message, else None."""
    text = str(raw or "").strip()
    low = text.lower()
    if low == "/talk":
        return ""
    if low.startswith("/talk "):
        return text[6:].strip()
    return None


def _is_disregarded_message(row: dict[str, Any]) -> bool:
    feedback = row.get("feedback") if isinstance(row, dict) else {}
    if isinstance(feedback, dict) and bool(feedback.get("disregard", False)):
        return True
    meta = row.get("meta") if isinstance(row, dict) else {}
    if isinstance(meta, dict) and bool(meta.get("disregard_context", False)):
        return True
    return False


def build_talk_history(messages: list[dict[str, Any]], limit_turns: int = 16) -> list[dict[str, str]]:
    """Build an LLM history list for follow-up talk turns across mixed lanes."""
    rows = messages[-max(40, limit_turns * 4):]
    out: list[dict[str, str]] = []
    for row in rows:
        if not isinstance(row, dict) or _is_disregarded_message(row):
            continue
        role = str(row.get("role", "")).strip().lower()
        content = str(row.get("content", "")).strip()
        mode = str(row.get("mode", "")).strip().lower()
        if role not in {"user", "assistant"} or not content:
            continue

        if role == "user":
            if mode == "talk":
                talk_text = content
            else:
                talk_text = extract_talk_text(content)
                if talk_text is None:
                    low = content.lower()
                    if low.startswith("/"):
                        # Keep only explicit /talk payload from slash commands.
                        continue
                    talk_text = content
            talk_text = str(talk_text or "").strip()
            if not talk_text:
                continue
            out.append({"role": "user", "content": talk_text})
            continue

        # Always keep assistant replies across modes; they carry thread substance.
        if len(content) > 3000:
            content = content[:3000].rstrip() + "\n[...truncated]"
        out.append({"role": "assistant", "content": content})

    max_messages = max(2, limit_turns * 2)
    return out[-max_messages:]


def build_command_history(messages: list[dict[str, Any]], limit_turns: int = 16) -> list[dict[str, str]]:
    """Build an LLM history list for command/research context (excludes talk, control commands)."""
    rows = messages[-max(24, limit_turns * 4):]
    out: list[dict[str, str]] = []
    for row in rows:
        if not isinstance(row, dict) or _is_disregarded_message(row):
            continue
        role = str(row.get("role", "")).strip().lower()
        content = str(row.get("content", "")).strip()
        mode = str(row.get("mode", "")).strip().lower()
        if role not in {"user", "assistant"} or not content:
            continue

        if role == "user":
            if mode and mode != "command":
                continue
            low = content.lower()
            if low.startswith("/talk"):
                continue
            if low.startswith("/") and low not in {"/status", "/models", "/local-models"}:
                continue
        out.append({"role": role, "content": content})

    max_messages = max(4, limit_turns * 2)
    return out[-max_messages:]


def build_fact_history(messages: list[dict[str, Any]], limit_turns: int = 120) -> list[dict[str, str]]:
    """Build a history list of user messages only for project fact extraction."""
    rows = messages[-max(80, limit_turns * 4):]
    out: list[dict[str, str]] = []
    for row in rows:
        if not isinstance(row, dict) or _is_disregarded_message(row):
            continue
        role = str(row.get("role", "")).strip().lower()
        content = str(row.get("content", "")).strip()
        if role != "user" or not content:
            continue

        talk_text = extract_talk_text(content)
        normalized = talk_text if talk_text is not None else content
        normalized = str(normalized or "").strip()
        if not normalized:
            continue

        low = normalized.lower()
        if low.startswith("/") and low not in {"/status", "/models", "/local-models"}:
            continue
        out.append({"role": "user", "content": normalized})

    max_messages = max(10, limit_turns * 2)
    return out[-max_messages:]
