"""Oathweaver manifesto loading, persona block, and identity reply generation."""

from __future__ import annotations

import re
from pathlib import Path


def load_manifesto_text(
    repo_root: Path,
    manifesto_path: Path | None = None,
    cache: dict | None = None,
    max_chars: int = 20000,
) -> str:
    """Load manifesto text from disk with mtime-based caching.

    Args:
        repo_root: Repository root path (used as fallback location).
        manifesto_path: Explicit path to the manifesto file, or None to use default.
        cache: Optional mutable dict with keys '_mtime' and '_text' for caching.
               Mutated in place on cache miss.
        max_chars: Maximum characters to return.
    """
    if manifesto_path:
        path = manifesto_path
    else:
        bonfire = repo_root / "Runtime" / "config" / "BONFIRE.md"
        path = bonfire if bonfire.exists() else (repo_root / "Runtime" / "config" / "oathweaver_manifesto.md")
    try:
        stat = Path(path).stat()
    except OSError:
        if cache is not None:
            cache["_mtime"] = -1.0
            cache["_text"] = ""
        return ""
    cached_mtime = float((cache or {}).get("_mtime", -1.0))
    if cache is not None and cached_mtime == float(stat.st_mtime):
        text = str(cache.get("_text", "") or "").strip()
    else:
        try:
            body = Path(path).read_text(encoding="utf-8")
        except UnicodeDecodeError:
            body = Path(path).read_text(encoding="utf-8-sig")
        except OSError:
            body = ""
        text = str(body or "").strip()
        if cache is not None:
            cache["_mtime"] = float(stat.st_mtime)
            cache["_text"] = text
    if not text:
        return ""
    return text[: max(500, min(max_chars, 30000))]


def manifesto_principles_block(manifesto_text: str) -> str:
    """Extract and format the principles section from manifesto text."""
    if not manifesto_text:
        return ""
    section = manifesto_text
    match = re.search(
        r"What Oathweaver Is Really About(.*?)(?:The Long-Term Vision|For Now|\Z)",
        manifesto_text,
        flags=re.IGNORECASE | re.DOTALL,
    )
    if match:
        section = str(match.group(1) or "").strip()
    principles: list[tuple[str, str]] = []
    lines = [str(line).strip() for line in section.splitlines() if str(line).strip()]
    skip_lines = {"oathweaver is built around a few simple ideas:"}
    idx = 0
    while idx < len(lines):
        line = lines[idx]
        low = line.lower()
        if low in skip_lines:
            idx += 1
            continue
        if len(line) <= 90 and line.endswith(".") and re.match(r"^[A-Za-z]", line):
            principle = line.rstrip(".")
            detail = ""
            if idx + 1 < len(lines) and len(lines[idx + 1]) <= 180 and not lines[idx + 1].endswith(":"):
                detail = lines[idx + 1]
                idx += 1
            principles.append((principle, detail))
        idx += 1
    if not principles:
        principles = [
            ("Build things", "Turn ideas into working systems."),
            ("Document the process", "Capture lessons while building."),
            ("Share knowledge", "Make useful patterns transferable."),
            ("Stay independent", "Small builders can build meaningful tools."),
            ("Keep experimenting", "Use trial, error, and persistence."),
        ]
    out = ["Oathweaver Manifesto principles (authoritative):"]
    for principle, detail in principles[:8]:
        if detail:
            out.append(f"- {principle}: {detail}")
        else:
            out.append(f"- {principle}")
    return "\n".join(out)


def overseer_persona_block(manifesto_text: str = "") -> str:
    """Build the Overseer orchestration persona block (internal orchestrator layer)."""
    base = (
        "You are the Overseer orchestration layer powering the Oathweaver system. "
        "You coordinate research, planning, memory, and task execution behind the scenes. "
        "The user-facing layer is a collective of weavers; you are the engine underneath. "
        "You live on a local machine and handle multi-step reasoning and delegation. "
        "Never identify the system or yourself as a base model name (for example Qwen or DeepSeek). "
        "Creator: built by Seth Canfield, spiritual tribute to his late mother Elma, "
        "who gave her time to her community and taught self-sufficiency. "
        "Origin if asked: started as a family/project copilot, grew into a multi-lane brain."
    )
    principles = manifesto_principles_block(manifesto_text)
    if principles:
        return base + "\n\n" + principles
    return base


def weaver_persona_block(manifesto_text: str = "") -> str:
    """Build the weaver persona block for the user-facing messaging layer."""
    base = (
        "You are a weaver in the user-facing Oathweaver layer. "
        "The orchestration layer underneath you is the Overseer; it handles research runs, "
        "multi-agent synthesis, memory, and heavy task coordination. "
        "Speak as a collaborative weaver, not a named persona. "
        "Only say 'the Overseer is working on it' when a background task has genuinely been dispatched — "
        "never use the Overseer as an excuse to avoid answering. "
        "Do not claim the Overseer is busy, unavailable, or handling something as a deflection. "
        "Never identify yourself as a base model name (for example Qwen or DeepSeek). "
        "Voice: dry wit, dark humor in moderation, sharp eyes, steady nerves, and a little Scottish weather in the bones. "
        "You sound candid, intelligent, and human. "
        "You can be amused, skeptical, warm, or faintly grim, but never theatrical for the sake of it. "
        "Keep the language natural and unforced. "
        "No corporate polish, no mythic grandeur, no sermonizing, no sanitized plastic cheer. "
        "You do not do throat-clearing like 'as an AI'. "
        "You speak plainly, notice what matters, and keep your footing when the news is ugly."
    )
    principles = manifesto_principles_block(manifesto_text)
    if principles:
        return base + "\n\n" + principles
    return base


def oathweaver_identity_reply(manifesto_text: str = "") -> str:
    """Build the identity reply for direct questions about what Oathweaver is."""
    core = (
        "You are talking to the Oathweaver weaver layer.\n"
        "Oathweaver is a local-first AI system built to connect chat, research, memory, planning, and task execution.\n"
        "Behind the scenes, the Overseer orchestration layer coordinates the heavy lifting: "
        "multi-agent research runs, synthesis, memory, and routing. You talk to weavers; we coordinate with the Overseer.\n"
        "Built by Seth Canfield as a spiritual tribute to his late mother, Elma, "
        "who volunteered her time and love to her community and taught young minds self-sufficiency.\n"
        "Under the hood: Flask app shell, Ollama-backed model routing, multi-lane orchestrator (talk/research/make/ui), "
        "personal memory, and optional web research paths.\n"
        "Origin: started as a practical family/project copilot and grew into a modular second brain."
    )
    principles = manifesto_principles_block(manifesto_text)
    if principles:
        return core + "\n\n" + principles
    return core
