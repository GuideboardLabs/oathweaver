"""Creative writing pool — novels, memoirs, books, screenplays.

Pipeline:
    1. Story Planner  — qwen3:8b outlines narrative arc, scenes, character beats.
    2. Scene Writer    — qwen3:8b (temp 0.7) drafts scenes sequentially with
                         prior scene context for continuity.
    3. Voice Critic    — qwen3:8b checks tense drift, POV breaks, pacing,
                         dialogue authenticity.
    4. Revision Pass   — qwen3:8b applies critic notes to flagged scenes.
    5. Compositor      — qwen3:8b assembles final chapter with smooth transitions.

Kind-specific formatting:
    - novel:      scene headers, dialogue, interior monologue, chapter hooks
    - memoir:     first-person voice, reflective passages, temporal anchoring
    - book:       thesis-driven chapters, evidence integration
    - screenplay: INT./EXT. headings, action lines, character cues, dialogue
"""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

from core.output_contracts import OutputContract, OutputContractAuditor
from shared_tools.fidelity_policy import FidelityLevel, fidelity_for, writer_constraint_block, thin_research_warning
from shared_tools.llm_retry import chat_with_self_fix_retry
from shared_tools.ollama_client import OllamaClient


_MODEL_PLANNER    = "qwen3:8b"
_MODEL_WRITER     = "qwen3:8b"
_MODEL_CRITIC     = "qwen3:8b"
_MODEL_COMPOSITOR = "qwen3:8b"
_CONTRACT_AUDITOR = OutputContractAuditor()


def _today() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d")


def _trim(text: str, max_chars: int) -> str:
    body = str(text or "").strip()
    if len(body) <= max_chars:
        return body
    cut = body[:max_chars].rsplit("\n", 1)[0].strip()
    return cut or body[:max_chars]


def _text_contract_validator(
    *,
    stage: str,
    required_markers: tuple[str, ...] = tuple(),
    forbidden_markers: tuple[str, ...] = tuple(),
    min_chars: int = 0,
) -> Callable[[str], str | None]:
    required = tuple(str(x) for x in required_markers if str(x))
    forbidden = tuple(str(x) for x in forbidden_markers if str(x))
    contract = OutputContract(stage=stage, must_include=required, must_not_include=forbidden)

    def _validate(text: str) -> str | None:
        raw = str(text or "").strip()
        if len(raw) < int(min_chars):
            return f"{stage}:too_short:{len(raw)}<{int(min_chars)}"
        payload: dict[str, Any] = {}
        for marker in required:
            payload[marker] = marker if marker in raw else ""
        for marker in forbidden:
            payload[marker] = marker if marker in raw else ""
        audit = _CONTRACT_AUDITOR.validate(stage, payload, contract)
        if audit.ok:
            return None
        missing = ",".join(audit.missing_fields)
        forbidden_fields = ",".join(audit.forbidden_fields)
        return f"{stage}:missing={missing};forbidden={forbidden_fields}"

    return _validate


_KIND_INSTRUCTIONS: dict[str, str] = {
    "novel": (
        "Write literary fiction. Use scene headers (### Scene N: <title>), "
        "rich dialogue with attribution, interior monologue in italics, "
        "sensory detail, and end each scene with a hook that pulls forward."
    ),
    "memoir": (
        "Write in intimate first-person voice. Anchor events in specific time and place. "
        "Weave reflective passages between narrative action. Use present tense for immediacy "
        "in key moments, past tense for framing. Be honest and vulnerable."
    ),
    "book": (
        "Write non-fiction with authority. Lead each section with a clear thesis. "
        "Integrate evidence smoothly. Address the reader directly when appropriate. "
        "Use subheadings for navigation. End sections with forward momentum."
    ),
    "screenplay": (
        "Use standard screenplay format: FADE IN, scene headings (INT./EXT. LOCATION - TIME), "
        "action lines in present tense, CHARACTER NAME centered above dialogue, "
        "parentheticals sparingly, transitions (CUT TO:, DISSOLVE TO:). "
        "Show, don't tell. Keep action lines tight — 3 lines max per block."
    ),
}


# ---------------------------------------------------------------------------
# Pipeline steps
# ---------------------------------------------------------------------------

def _run_story_planner(
    client: OllamaClient,
    question: str,
    kind: str,
    research_context: str,
    level: FidelityLevel = FidelityLevel.CREATIVE,
) -> str:
    kind_note = _KIND_INSTRUCTIONS.get(kind, _KIND_INSTRUCTIONS["novel"])
    thin_warn = thin_research_warning(level, len(research_context))
    system_prompt = (
        f"Today: {_today()}. "
        "You are a story architect. Given a writing request and any research/project context, "
        "produce a detailed scene-by-scene outline for a single chapter or episode. "
        "For each scene, specify: (1) setting, (2) characters present, (3) the dramatic question, "
        "(4) key beats, (5) emotional arc, (6) how it transitions to the next scene. "
        f"\n\nFormat note for '{kind}': {kind_note}\n\n"
        f"Output format: '### Scene N: <title>\\n<outline details>'. Nothing else.{thin_warn}"
    )
    user_prompt = (
        f"Kind: {kind}\nRequest: {question}\n\n"
        f"Research context:\n{_trim(research_context, 8000)}"
    )
    try:
        result = chat_with_self_fix_retry(
            client,
            model=_MODEL_PLANNER,
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            temperature=0.4,
            num_ctx=16384,
            think=False,
            timeout=300,
            retry_attempts=4,
            retry_backoff_sec=1.5,
            validator=_text_contract_validator(
                stage="creative_story_planner",
                required_markers=("### Scene",),
                min_chars=80,
            ),
        )
        return str(result.text or "").strip()
    except Exception:
        return f"### Scene 1: Opening\nEstablish setting and characters based on: {question[:200]}"


def _run_scene_writer(
    client: OllamaClient,
    scene_name: str,
    scene_outline: str,
    full_plan: str,
    prior_scene_text: str,
    question: str,
    kind: str,
    research_context: str,
    level: FidelityLevel = FidelityLevel.CREATIVE,
) -> str:
    kind_note = _KIND_INSTRUCTIONS.get(kind, _KIND_INSTRUCTIONS["novel"])
    continuity_block = ""
    if prior_scene_text:
        continuity_block = (
            f"\n\nPrevious scene ending (maintain continuity):\n"
            f"{_trim(prior_scene_text, 2000)}"
        )
    system_prompt = (
        f"Today: {_today()}. "
        f"You are a {kind} writer. Write ONE scene only — approximately 800-1200 words. "
        f"Style: {kind_note}\n\n"
        f"{writer_constraint_block(level)} "
        "Write in flowing, immersive prose. Do not include meta-commentary. "
        "Do not start with the scene header — the compositor handles that."
    )
    user_prompt = (
        f"Full chapter plan (for context — write ONLY your assigned scene):\n{_trim(full_plan, 2000)}\n\n"
        f"YOUR SCENE: {scene_name}\n"
        f"Scene outline: {scene_outline}\n\n"
        f"Research context:\n{_trim(research_context, 6000)}\n\n"
        f"Original request: {question}"
        f"{continuity_block}"
    )
    try:
        result = chat_with_self_fix_retry(
            client,
            model=_MODEL_WRITER,
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            temperature=0.7,
            num_ctx=20480,
            think=False,
            timeout=420,
            retry_attempts=4,
            retry_backoff_sec=2.0,
            validator=_text_contract_validator(
                stage="creative_scene_writer",
                forbidden_markers=("[Scene generation failed",),
                min_chars=200,
            ),
        )
        return str(result.text or "").strip()
    except Exception as exc:
        return f"[Scene generation failed: {exc}]"


def _run_voice_critic(
    client: OllamaClient,
    scenes_text: str,
    question: str,
    kind: str,
) -> str:
    system_prompt = (
        f"Today: {_today()}. "
        f"You are a literary editor reviewing a {kind} draft. Check specifically for:\n"
        "1. Tense drift (switching between past/present without intention)\n"
        "2. POV breaks (head-hopping, inconsistent narrative distance)\n"
        "3. Pacing issues (scenes that drag or rush)\n"
        "4. Dialogue authenticity (stilted speech, missing distinct voices)\n"
        "5. Show vs tell violations (telling emotions instead of showing them)\n"
        "6. Continuity errors between scenes\n\n"
        "For each issue: name the scene and give a specific fix instruction. "
        "If the draft is strong, say 'No major issues found.' and stop."
    )
    user_prompt = (
        f"Kind: {kind} | Request: {question}\n\n"
        f"Draft to review:\n{_trim(scenes_text, 16000)}"
    )
    try:
        result = chat_with_self_fix_retry(
            client,
            model=_MODEL_CRITIC,
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            temperature=0.1,
            num_ctx=24576,
            think=False,
            timeout=360,
            retry_attempts=3,
            retry_backoff_sec=1.5,
            validator=_text_contract_validator(
                stage="creative_voice_critic",
                min_chars=20,
            ),
        )
        return str(result.text or "").strip()
    except Exception as exc:
        return f"[Voice critic failed: {exc}]"


def _run_scene_revision(
    client: OllamaClient,
    scene_name: str,
    scene_text: str,
    critic_notes: str,
    kind: str,
) -> str:
    system_prompt = (
        f"You are a {kind} editor. Apply the critic's notes to improve this scene. "
        "Preserve the voice, tone, and approximate length. "
        "Return the complete revised scene text only."
    )
    user_prompt = (
        f"Scene: {scene_name}\n\n"
        f"Current text:\n{scene_text}\n\n"
        f"Critic notes:\n{_trim(critic_notes, 1500)}"
    )
    try:
        result = chat_with_self_fix_retry(
            client,
            model=_MODEL_WRITER,
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            temperature=0.5,
            num_ctx=16384,
            think=False,
            timeout=300,
            retry_attempts=3,
            retry_backoff_sec=1.5,
            validator=_text_contract_validator(
                stage="creative_scene_revision",
                min_chars=80,
            ),
        )
        return str(result.text or "").strip() or scene_text
    except Exception:
        return scene_text


def _run_compositor(
    client: OllamaClient,
    scenes: list[tuple[str, str]],
    scene_texts: dict[str, str],
    question: str,
    kind: str,
) -> str:
    assembled_parts: list[str] = []
    for name, _ in scenes:
        text = scene_texts.get(name, "").strip()
        if text:
            assembled_parts.append(f"### {name}\n\n{text}")
    assembled = "\n\n---\n\n".join(assembled_parts)

    kind_note = _KIND_INSTRUCTIONS.get(kind, _KIND_INSTRUCTIONS["novel"])
    system_prompt = (
        f"Today: {_today()}. "
        f"You are a final compositor for a {kind}. You receive labelled scenes and produce "
        "a polished, unified chapter. Tasks:\n"
        "1. Write a compelling chapter title.\n"
        "2. Smooth transitions between scenes — no abrupt jumps.\n"
        "3. Ensure consistent voice, tense, and narrative distance throughout.\n"
        "4. End with a hook or resonant closing line.\n"
        f"5. Apply format conventions: {kind_note}\n\n"
        "Output clean markdown. Use ## for the chapter title, ### for scene breaks. "
        "No meta-commentary."
    )
    user_prompt = (
        f"Kind: {kind}\nOriginal request: {question}\n\n"
        f"Scenes to assemble:\n\n{assembled}"
    )
    try:
        result = chat_with_self_fix_retry(
            client,
            model=_MODEL_COMPOSITOR,
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            temperature=0.4,
            num_ctx=24576,
            think=False,
            timeout=480,
            retry_attempts=4,
            retry_backoff_sec=2.0,
            validator=_text_contract_validator(
                stage="creative_compositor",
                required_markers=("##", "###"),
                min_chars=240,
            ),
        )
        return str(result.text or "").strip()
    except Exception:
        fallback_lines = [f"# {question[:80]}", ""]
        for name, _ in scenes:
            text = scene_texts.get(name, "").strip()
            if text:
                fallback_lines.append(f"## {name}\n\n{text}")
        return "\n\n".join(fallback_lines)


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------

def run_creative_pool(
    question: str,
    repo_root: Path,
    project_slug: str,
    bus: Any,
    target: str = "novel",
    topic_type: str = "general",
    research_context: str = "",
    cancel_checker: Callable[[], bool] | None = None,
    progress_callback: Callable[[str, dict[str, Any]], None] | None = None,
) -> dict[str, Any]:
    """Run the full creative writing pipeline and return assembled text."""

    def _progress(stage: str, detail: dict[str, Any] | None = None) -> None:
        if callable(progress_callback):
            try:
                progress_callback(stage, detail or {})
            except Exception:
                pass

    def _cancelled() -> bool:
        if callable(cancel_checker):
            try:
                return bool(cancel_checker())
            except Exception:
                return False
        return False

    kind = str(target).strip().lower() or "novel"
    _level = fidelity_for(kind, topic_type)
    bus.emit("creative_pool", "start", {"question": question, "target": kind})

    client = OllamaClient()

    # Step 1: Story plan
    if _cancelled():
        return {"ok": False, "message": "Cancelled before planning.", "body": ""}

    _progress("creative_planner_started", {"kind": kind})
    plan = _run_story_planner(client, question, kind, research_context, _level)
    _progress("creative_planner_completed", {"preview": plan[:300]})

    # Parse plan into scenes
    scenes: list[tuple[str, str]] = []
    current_name: str | None = None
    current_lines: list[str] = []
    for line in plan.splitlines():
        stripped = line.strip()
        if stripped.startswith("###"):
            if current_name is not None:
                scenes.append((current_name, " ".join(current_lines).strip()))
            current_name = stripped.lstrip("#").strip()
            current_lines = []
        elif current_name is not None and stripped:
            current_lines.append(stripped)
    if current_name is not None:
        scenes.append((current_name, " ".join(current_lines).strip()))

    if not scenes:
        scenes = [("Scene 1: Opening", f"Write the opening based on: {question[:200]}")]

    # Step 2: Sequential scene writing (continuity matters)
    scene_texts: dict[str, str] = {}
    prior_text = ""
    for i, (scene_name, scene_outline) in enumerate(scenes):
        if _cancelled():
            return {"ok": False, "message": "Cancelled during scene writing.", "body": ""}
        _progress("creative_scene_started", {
            "scene": scene_name, "index": i + 1, "total": len(scenes),
        })
        text = _run_scene_writer(
            client, scene_name, scene_outline, plan,
            prior_text, question, kind, research_context, _level,
        )
        scene_texts[scene_name] = text
        prior_text = text[-1500:] if text else ""
        _progress("creative_scene_completed", {
            "scene": scene_name, "index": i + 1, "total": len(scenes),
            "preview": text[:200],
        })

    # Step 3: Voice critic
    if _cancelled():
        return {"ok": False, "message": "Cancelled before critic.", "body": ""}

    all_scenes_text = "\n\n".join(
        f"### {name}\n\n{scene_texts.get(name, '')}" for name, _ in scenes
    )
    _progress("creative_critic_started", {})
    critic_notes = _run_voice_critic(client, all_scenes_text, question, kind)
    _progress("creative_critic_completed", {"preview": critic_notes[:300]})

    # Step 4: Revision pass on flagged scenes
    if critic_notes and "no major issues" not in critic_notes.lower() and not _cancelled():
        flagged: list[str] = []
        for name, _ in scenes:
            if name.lower() in critic_notes.lower():
                flagged.append(name)
        if flagged:
            _progress("creative_revision_started", {"scenes_flagged": flagged})
            for scene_name in flagged:
                if _cancelled():
                    break
                revised = _run_scene_revision(
                    client, scene_name, scene_texts.get(scene_name, ""),
                    critic_notes, kind,
                )
                scene_texts[scene_name] = revised
            _progress("creative_revision_completed", {"scenes_revised": len(flagged)})

    # Step 5: Compositor
    if _cancelled():
        return {"ok": False, "message": "Cancelled before compositor.", "body": ""}

    _progress("creative_compositor_started", {"total_scenes": len(scenes)})
    final_body = _run_compositor(client, scenes, scene_texts, question, kind)
    _progress("creative_compositor_completed", {"chars": len(final_body)})

    bus.emit("creative_pool", "completed", {
        "project": project_slug, "target": kind, "chars": len(final_body),
    })

    return {
        "ok": True,
        "body": final_body,
        "plan": plan,
        "critic_notes": critic_notes,
        "scenes_written": list(scene_texts.keys()),
        "message": f"{kind.title()} chapter complete — {len(final_body):,} chars, {len(scenes)} scenes.",
    }
