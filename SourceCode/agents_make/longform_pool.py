"""Longform pool — long-form essays, video scripts, guides, tutorials, newsletters, press releases.

Pipeline (6 stages, mirrors research sophistication):
    1. Planner    — outlines structure using process_note guardrail + type-specific template
    2. Writers    — parallel section writers (≤3 workers), grounded in research context
    3. Critic     — deepseek-r1:8b with think=True, identifies gaps / structural issues
    4. Revisor    — applies critic notes to flagged sections only
    5. Compositor — assembles final piece: title, transitions, consistent voice, conclusion
    6. Gate       — length / structure validation, auto-fix if needed

Type-specific section templates and process notes ensure each output type has
the right shape (e.g., video scripts get [SEGMENT] / [B-ROLL] markers, newsletters
get the four-section digest format, guides get the prereqs→steps→verify structure).
"""

from __future__ import annotations

import re
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

from agents_research.synthesizer import run_skeptic_pass_with_severity
from core.output_contracts import OutputContract, OutputContractAuditor
from shared_tools.feedback_learning import FeedbackLearningEngine
from shared_tools.fidelity_policy import FidelityLevel, fidelity_for, writer_constraint_block, evidence_key_block, critic_fabrication_block, planner_grounding_rule, thin_research_warning
from shared_tools.inference_router import InferenceRouter
from shared_tools.llm_retry import chat_with_self_fix_retry
from shared_tools.loop_controller import run_draft_critique_revise
from shared_tools.model_routing import lane_model_config


# ---------------------------------------------------------------------------
# Models
# ---------------------------------------------------------------------------

_MODEL_PLANNER    = "qwen3:8b"
_MODEL_WRITER     = "qwen3:8b"
_MODEL_CRITIC     = "deepseek-r1:8b"
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


def _contract_validator(
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
        return f"{stage}:missing={','.join(audit.missing_fields)};forbidden={','.join(audit.forbidden_fields)}"

    return _validate


# ---------------------------------------------------------------------------
# Type-specific section templates and metadata
# ---------------------------------------------------------------------------

_TYPE_SPECS: dict[str, dict[str, Any]] = {
    "essay_long": {
        "word_range": "1800–3500 words",
        "sections": [
            ("Hook & Lede",              "Open with a narrative hook or striking claim that earns the reader's attention. State the thesis by the end of this section."),
            ("Background & Context",     "The necessary context a reader needs to follow the argument. Establish stakes."),
            ("Argument Pillar 1",        "First major supporting argument. Specific evidence, examples, or case studies."),
            ("Argument Pillar 2",        "Second major supporting argument. Deepens or pivots from Pillar 1."),
            ("Argument Pillar 3",        "Third major supporting argument. Can introduce the strongest evidence."),
            ("Steelman & Counterpoint",  "The best counterargument, stated fairly. Acknowledge what it gets right, then rebut."),
            ("Synthesis & So-What",      "Tie the pillars together. What does this mean? Why does it matter now?"),
            ("Close",                    "Memorable closing. Callback to the lede, a challenge, or a forward-looking statement."),
        ],
        "process_note": (
            "Thesis → 3–5 argument pillars each with evidence → steelman counterargument → "
            "synthesis → so-what → memorable close. Uses narrative hook in lede. "
            "Each section earns the next. Cut anything that slows the argument."
        ),
    },
    "essay_short": {
        "word_range": "400–900 words",
        "sections": [
            ("Hook",        "One strong opening move — a story, a claim, or a question. Draws the reader in."),
            ("Argument",    "The core thesis with 2–3 supporting points. Concrete and specific."),
            ("Counterpoint","One honest counterpoint, addressed briefly."),
            ("Close",       "Tight, punchy close. What's the takeaway? What should the reader do or think differently?"),
        ],
        "process_note": (
            "One strong thesis, stated early. Two or three argument beats with concrete detail. "
            "Steelman one counterpoint. Strong close. Voice is personal and direct. "
            "Designed to be read in under 4 minutes."
        ),
    },
    "guide": {
        "word_range": "1000–2500 words",
        "sections": [
            ("Overview & Prerequisites",  "What this guide covers, who it is for, and what the reader needs before starting."),
            ("What You'll Learn",         "Bullet list of skills or knowledge the reader will have after completing this guide."),
            ("Step 1",                    "First major step. Clear action, exact commands or examples where relevant, expected outcome."),
            ("Step 2",                    "Second major step. Continue the sequence."),
            ("Step 3",                    "Third major step. Include gotchas or common mistakes to avoid."),
            ("Verification",              "How the reader confirms everything is working. What success looks like."),
            ("Next Steps",               "Where to go from here. Related guides, advanced topics, or community resources."),
        ],
        "process_note": (
            "Prereqs callout → 'what you'll learn' → steps with exact commands → "
            "common pitfalls block per step → verification step → next steps. "
            "Assume reader skims first: H2/H3 structure + callout blocks. "
            "Writes well in markdown; converts cleanly to Word via Pandoc."
        ),
    },
    "tutorial": {
        "word_range": "1200–3000 words",
        "sections": [
            ("Goal & Prerequisites",     "What you'll build by the end and what's needed to follow along. Install prerequisites here."),
            ("Step 1: Setup",            "First hands-on step. Code block ready to copy-paste. 'You should see:' verification."),
            ("Step 2: Core Logic",       "The main implementation step. Code block with explanation of each key line."),
            ("Step 3: Integration",      "Connecting the pieces. Verification that everything works together."),
            ("Step 4: Polish & Edge Cases", "Making it robust. Handle error cases. 'You should see:' verification."),
            ("Troubleshooting",          "Most common errors and their fixes. Exact error messages where possible."),
            ("What You Built & Next Steps", "Summary of what was accomplished, link to finished code, next complexity levels."),
        ],
        "process_note": (
            "Goal statement → prereqs → numbered steps with runnable code blocks → "
            "'you should see' verification after each major step → troubleshooting block → next steps. "
            "Code blocks are copy-paste ready. Teaches a specific task, not a concept."
        ),
    },
    "video_script": {
        "word_range": "1500–4000 words (read-aloud ~10–20 min)",
        "sections": [
            ("[SEGMENT: Hook]",         "0–15 seconds. One striking statement, question, or clip that earns the next 60 seconds of viewer attention."),
            ("[SEGMENT: Premise]",      "15–45 seconds. Set up the video's core promise: what will the viewer learn or feel?"),
            ("[SEGMENT: Beat 1]",       "First major content beat. Clear setup → payoff structure. [B-ROLL SUGGESTION: ...] markers included."),
            ("[SEGMENT: Beat 2]",       "Second major content beat. Deepens or pivots from Beat 1."),
            ("[SEGMENT: Beat 3]",       "Third major content beat. The strongest argument or most surprising moment."),
            ("[SEGMENT: Turn/Reveal]",  "The pivot or insight that reframes what came before. Not mandatory but powerful."),
            ("[SEGMENT: Close & CTA]",  "Landing the plane. What should the viewer take away or do? Specific CTA."),
        ],
        "process_note": (
            "Hook (0–15s) → premise (15–45s) → body in 3–5 beats with visual pacing notes → "
            "turn/reveal → close with CTA. Every sentence is read aloud — prefer short "
            "sentences, conversational rhythm, avoid words that trip on the tongue. "
            "Use [SEGMENT: title] markers for chapter cuts, [B-ROLL: description] for visual suggestions."
        ),
    },
    "newsletter": {
        "word_range": "600–1200 words",
        "sections": [
            ("Subject & Preview Text",  "The email subject line and the 80-char preview text that shows in inboxes."),
            ("This Week",               "2–3 news items or developments with a quick take on each. Curated, not comprehensive."),
            ("Worth Your Time",         "2–3 external links with a sentence on why each is worth reading."),
            ("One Idea",                "The core insight or argument of this edition. 200–400 words, original voice."),
            ("Dessert",                 "Something lighter to close — a quote, a weird fact, a recommendation. 1–3 sentences."),
        ],
        "process_note": (
            "Standing sections: This Week / Worth Your Time / One Idea / Dessert. "
            "Voice consistent across editions. Hook in the first two lines of the email preview. "
            "Each section self-contained — readers pick and choose."
        ),
    },
    "press_release": {
        "word_range": "400–700 words",
        "sections": [
            ("Headline",    "Attention-grabbing headline in AP style. Active voice. Under 90 characters."),
            ("Dateline",    "City, State — Date format. E.g., 'SEATTLE, WA — April 17, 2026'"),
            ("Lede",        "Who/what/when/where/why in the first two sentences. The most important information first."),
            ("Body",        "2–3 paragraphs expanding the story. Include a quote from a stakeholder (use [NAME, TITLE] placeholder if not provided)."),
            ("Boilerplate", "Standard 'About [Org]' paragraph. Keep it under 75 words."),
            ("Contact",     "Media contact: Name, email, phone. Include ###  at the end to signal end of release."),
        ],
        "process_note": (
            "Headline → dateline → lede (who/what/when/where/why in two sentences) → "
            "2–3 body paragraphs with stakeholder quotes → org boilerplate → contact. "
            "Inverted pyramid: most important first."
        ),
    },
}


def _sections_for(type_id: str) -> list[tuple[str, str]]:
    spec = _TYPE_SPECS.get(type_id, _TYPE_SPECS["essay_long"])
    return spec["sections"]


def _word_range_for(type_id: str) -> str:
    spec = _TYPE_SPECS.get(type_id, _TYPE_SPECS["essay_long"])
    return spec["word_range"]


def _process_note_for(type_id: str) -> str:
    spec = _TYPE_SPECS.get(type_id, _TYPE_SPECS["essay_long"])
    return spec.get("process_note", "")


def _is_longform_type(type_id: str) -> bool:
    return type_id in {"essay_long", "video_script", "newsletter"}


# ---------------------------------------------------------------------------
# Pipeline steps
# ---------------------------------------------------------------------------

def _run_planner(
    client: InferenceRouter,
    question: str,
    type_id: str,
    sections: list[tuple[str, str]],
    research_context: str,
    level: FidelityLevel = FidelityLevel.STRICT,
) -> str:
    sections_text = "\n".join(f"- {name}: {hint}" for name, hint in sections)
    process_note = _process_note_for(type_id)
    grounding = planner_grounding_rule(level)
    thin_warn = thin_research_warning(level, len(research_context))
    grounding_block = f"\n{grounding}{thin_warn}\n" if (grounding or thin_warn) else ""
    system_prompt = (
        f"Today: {_today()}. You are an expert content planner.\n\n"
        f"Output type: {type_id.replace('_', ' ').title()}\n"
        f"Target length: {_word_range_for(type_id)}\n\n"
        f"Process guidance (how a skilled human produces this):\n{process_note}\n\n"
        "PUBLIC-CONTENT GUARDRAIL: This is public-facing content. Do not reference the author's private personal "
        "relationships, health conditions, workplace, or other personal specifics from profile hints unless the user explicitly "
        "asks for those specifics. Prefer category phrasing (for example: 'as a parent', 'as a caregiver').\n\n"
        "For each required section below, write a one-sentence thesis statement "
        "that is SPECIFIC to the user's request and grounded in the research context. "
        "Do not write generic filler — every thesis must reflect actual content.\n\n"
        f"Required sections:\n{sections_text}\n"
        f"{grounding_block}\n"
        "Format your response as:\n"
        "### [Section Name]\n[Specific thesis for this section]\n\n"
        "Do not write the content itself. Only the thesis map."
    )
    user_prompt = (
        f"Request: {question}\n\n"
        f"Research context:\n{_trim(research_context, 7000)}"
    )
    try:
        result = chat_with_self_fix_retry(
            client,
            model=_MODEL_PLANNER,
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            temperature=0.25,
            num_ctx=16384,
            think=False,
            timeout=240,
            retry_attempts=3,
            retry_backoff_sec=1.5,
            validator=_contract_validator(
                stage="longform_planner",
                required_markers=("###",),
                min_chars=100,
            ),
        )
        return str(result.text or "").strip()
    except Exception as exc:
        return f"[Planner failed: {exc}]"


def _run_section_writer(
    client: InferenceRouter,
    question: str,
    type_id: str,
    section_name: str,
    section_thesis: str,
    research_context: str,
    prior_section_preview: str = "",
    raw_notes_context: str = "",
    level: FidelityLevel = FidelityLevel.STRICT,
) -> tuple[str, str]:
    word_range = _word_range_for(type_id)
    process_note = _process_note_for(type_id)
    is_video = type_id == "video_script"
    video_note = (
        "\nThis is a VIDEO SCRIPT — write every sentence to be READ ALOUD. "
        "Short sentences. Conversational rhythm. Avoid tongue-twisters. "
        "Include [B-ROLL: description] markers to suggest visuals within the section."
    ) if is_video else ""

    system_prompt = (
        f"Today: {_today()}. You are an expert writer producing a {type_id.replace('_', ' ')} section.\n\n"
        f"Overall piece target length: {word_range}\n"
        f"Process guidance: {process_note}{video_note}\n\n"
        f"Write ONLY this section. {writer_constraint_block(level)} "
        "Do not include headings for other sections."
    )
    ev_key = evidence_key_block(level, bool(raw_notes_context.strip()))
    user_prompt_parts = [
        f"Original request: {question}",
        f"\nSection: {section_name}",
        f"Section focus: {section_thesis}",
    ]
    if prior_section_preview:
        user_prompt_parts.append(f"\nPrevious section (for continuity, do not repeat):\n{_trim(prior_section_preview, 600)}")
    user_prompt_parts.extend([
        f"\nResearch context:{ev_key}\n{_trim(research_context, 5000)}",
    ])
    try:
        result = chat_with_self_fix_retry(
            client,
            model=_MODEL_WRITER,
            system_prompt=system_prompt,
            user_prompt="\n".join(user_prompt_parts),
            temperature=0.55,
            num_ctx=16384,
            think=False,
            timeout=300,
            retry_attempts=3,
            retry_backoff_sec=1.5,
            validator=_contract_validator(
                stage="longform_section_writer",
                min_chars=220,
            ),
        )
        return section_name, str(result.text or "").strip()
    except Exception as exc:
        return section_name, f"[Section '{section_name}' failed: {exc}]"


def _run_critic(
    client: InferenceRouter,
    assembled: str,
    type_id: str,
    question: str,
    raw_notes_context: str = "",
    level: FidelityLevel = FidelityLevel.STRICT,
    research_context: str = "",
) -> str:
    process_note = _process_note_for(type_id)
    raw_block = critic_fabrication_block(level, raw_notes_context, _trim, research_context)
    system_prompt = (
        f"You are a critical editor for a {type_id.replace('_', ' ')}.\n\n"
        f"Process standard: {process_note}\n\n"
        "Review the draft for:\n"
        "1. Structural gaps — missing sections or sections that don't follow the process standard\n"
        "2. Repetition — content that appears in multiple sections without adding new value\n"
        "3. Unsupported claims — specific assertions (names, dates, stats, events) not traceable to the research context\n"
        "4. Thesis drift — sections that wander from the original request\n"
        "5. Voice inconsistency — tense drift, POV breaks, or register mismatches\n"
        "6. Truncation — sections that end abruptly or feel incomplete\n\n"
        "For each issue: write '**[Section Name]**: [one-sentence fix instruction]'\n"
        "If the draft meets the standard, write 'Approved.' and stop.\n"
        "Be blunt. Only flag real problems."
    )
    try:
        result = chat_with_self_fix_retry(
            client,
            model=_MODEL_CRITIC,
            system_prompt=system_prompt,
            user_prompt=f"Original request: {question}\n\nDraft:\n{_trim(assembled, 10000)}{raw_block}",
            temperature=0.1,
            num_ctx=24576,
            think=True,
            timeout=360,
            retry_attempts=3,
            retry_backoff_sec=2.0,
            validator=_contract_validator(
                stage="longform_critic",
                min_chars=24,
            ),
        )
        return str(result.text or "").strip()
    except Exception:
        return "Approved."


def _run_revisor(
    client: InferenceRouter,
    section_name: str,
    section_body: str,
    fix_note: str,
    type_id: str,
    question: str,
    research_context: str,
) -> str:
    system_prompt = (
        f"You are revising a single section of a {type_id.replace('_', ' ')}. "
        "Apply the editor's note precisely. Do not rewrite sections that weren't flagged. "
        "Return the complete revised section only."
    )
    user_prompt = (
        f"Section: {section_name}\n"
        f"Editor note: {fix_note}\n\n"
        f"Original request: {question}\n"
        f"Research context: {_trim(research_context, 3000)}\n\n"
        f"Section to revise:\n{section_body}"
    )
    try:
        result = chat_with_self_fix_retry(
            client,
            model=_MODEL_WRITER,
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            temperature=0.35,
            num_ctx=12288,
            think=False,
            timeout=240,
            retry_attempts=3,
            retry_backoff_sec=1.5,
            validator=_contract_validator(
                stage="longform_revisor",
                min_chars=120,
            ),
        )
        revised = str(result.text or "").strip()
        return revised if revised and len(revised) >= len(section_body) * 0.4 else section_body
    except Exception:
        return section_body


def _run_compositor(
    client: InferenceRouter,
    sections: list[tuple[str, str]],
    type_id: str,
    question: str,
    research_context: str,
) -> str:
    process_note = _process_note_for(type_id)
    sections_text = "\n\n".join(
        f"## {name}\n{body}" for name, body in sections if body
    )
    is_video = type_id == "video_script"
    special_note = (
        "\nFor VIDEO SCRIPT: Preserve all [SEGMENT: ...] and [B-ROLL: ...] markers exactly."
    ) if is_video else ""

    system_prompt = (
        f"You are a senior editor composing a final {type_id.replace('_', ' ')}.\n\n"
        f"Process standard: {process_note}{special_note}\n\n"
        "PUBLIC-CONTENT GUARDRAIL: This is public-facing content. Do not reference the author's private personal "
        "relationships, health conditions, workplace, or other personal specifics from profile hints unless the user explicitly "
        "asks for those specifics. Prefer category phrasing (for example: 'as a parent', 'as a caregiver').\n\n"
        "Assemble the sections into one polished final document:\n"
        "1. Add an appropriate title at the top\n"
        "2. Write smooth transitions between sections (1–2 sentences where needed)\n"
        "3. Ensure consistent voice and tense throughout\n"
        "4. REPETITION AUDIT: Scan every paragraph for content that restates an argument, "
        "claim, or phrase already made in a previous section. Delete the duplicate occurrence "
        "entirely — do not soften or vary it. Keep the version in the section where it fits best.\n"
        "5. Keep every section's core content intact — do not condense aggressively\n\n"
        "Return the complete assembled document in markdown. No meta-commentary."
    )
    try:
        result = chat_with_self_fix_retry(
            client,
            model=_MODEL_COMPOSITOR,
            system_prompt=system_prompt,
            user_prompt=f"Original request: {question}\n\n{sections_text}",
            temperature=0.3,
            num_ctx=24576,
            think=False,
            timeout=360,
            retry_attempts=3,
            retry_backoff_sec=1.5,
            validator=_contract_validator(
                stage="longform_compositor",
                required_markers=("##",),
                min_chars=320,
            ),
        )
        return str(result.text or "").strip()
    except Exception as exc:
        # Fallback: just join sections
        return "\n\n".join(f"## {n}\n\n{b}" for n, b in sections if b)


def _parse_critic_notes(critic_output: str, section_names: list[str]) -> dict[str, str]:
    """Parse critic notes into a dict of {section_name: fix_instruction}."""
    notes: dict[str, str] = {}
    if not critic_output or "approved" in critic_output.lower()[:50]:
        return notes
    pattern = re.compile(r'\*\*(.+?)\*\*\s*[:\-]\s*(.+?)(?=\n\*\*|\Z)', re.DOTALL)
    for match in pattern.finditer(critic_output):
        raw_name = match.group(1).strip()
        fix = match.group(2).strip()
        for name in section_names:
            if raw_name.lower() in name.lower() or name.lower() in raw_name.lower():
                notes[name] = fix[:500]
                break
    return notes


def _quality_gate(
    body: str,
    type_id: str,
) -> tuple[bool, list[str]]:
    """Check basic quality requirements. Returns (passed, issues)."""
    issues: list[str] = []
    min_chars = {
        "essay_long": 3000,
        "essay_short": 600,
        "guide": 1500,
        "tutorial": 2000,
        "video_script": 2500,
        "newsletter": 800,
        "press_release": 500,
    }.get(type_id, 800)

    if len(body) < min_chars:
        issues.append(f"Too short: {len(body)} chars (minimum {min_chars})")
    if body.endswith("...") or body.endswith("…"):
        issues.append("Appears truncated (ends with ellipsis)")
    if "TODO" in body or "[PLACEHOLDER]" in body.upper():
        issues.append("Contains unresolved TODO or placeholder markers")
    if type_id == "video_script" and "[SEGMENT:" not in body:
        issues.append("Missing [SEGMENT: ...] markers required for video scripts")
    return len(issues) == 0, issues


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------

def run_longform_pool(
    question: str,
    repo_root: Path,
    project_slug: str,
    bus: Any,
    type_id: str = "essay_long",
    topic_type: str = "general",
    research_context: str = "",
    raw_notes_context: str = "",
    sources_context: str = "",
    cancel_checker: Callable[[], bool] | None = None,
    progress_callback: Callable[[str, dict[str, Any]], None] | None = None,
) -> dict[str, Any]:
    """Run the full longform pipeline and return the assembled text."""

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

    type_id = str(type_id or "essay_long").strip().lower()
    if type_id not in _TYPE_SPECS:
        type_id = "essay_long"
    _level = fidelity_for(type_id, topic_type)

    bus.emit("longform_pool", "start", {"question": question, "type_id": type_id})

    combined_research = "\n\n".join(filter(None, [research_context, raw_notes_context, sources_context]))
    sections = _sections_for(type_id)
    section_names = [n for n, _ in sections]
    client = InferenceRouter(repo_root)

    # Learning integration
    orchestrator_cfg = lane_model_config(repo_root, "orchestrator_reasoning")
    try:
        learning = FeedbackLearningEngine(repo_root, client=client, model_cfg=orchestrator_cfg)
        learned_guidance = learning.guidance_for_lane("make_longform", limit=5)
        if learned_guidance:
            combined_research = (learned_guidance + "\n\n" + combined_research).strip()
    except Exception:
        pass

    total_agents = len(sections) + 4  # planner + writers + critic + revisor + compositor
    _progress("build_pool_started", {
        "stage": "build_pool_started",
        "agents_total": total_agents,
        "make_type": type_id,
        "destination": "Essays-Scripts",
    })

    # ------------------------------------------------------------------
    # Step 1: Planner
    # ------------------------------------------------------------------
    if _cancelled():
        return {"ok": False, "message": "Cancelled before planning.", "body": ""}

    _progress("build_agent_started", {"stage": "build_agent_started", "agent": "planner", "model": _MODEL_PLANNER})
    outline = _run_planner(client, question, type_id, sections, combined_research, _level)
    _progress("build_agent_completed", {"stage": "build_agent_completed", "agent": "planner", "output_chars": len(outline)})

    # Parse outline → section theses
    section_theses: dict[str, str] = {}
    current_section: str | None = None
    current_lines: list[str] = []
    for line in outline.splitlines():
        stripped = line.strip()
        if stripped.startswith("###"):
            if current_section is not None:
                section_theses[current_section] = " ".join(current_lines).strip()
            current_section = stripped.lstrip("#").strip()
            current_lines = []
        elif current_section is not None and stripped:
            current_lines.append(stripped)
    if current_section is not None:
        section_theses[current_section] = " ".join(current_lines).strip()

    # Fill fallbacks from template hints
    for name, hint in sections:
        if name not in section_theses or not section_theses[name]:
            section_theses[name] = hint

    # ------------------------------------------------------------------
    # Step 2: Parallel section writers
    # ------------------------------------------------------------------
    if _cancelled():
        return {"ok": False, "message": "Cancelled before writing.", "body": ""}

    _progress("essay_sections_started", {"sections": section_names, "workers": min(3, len(sections))})

    section_bodies: dict[str, str] = {}
    sections_to_write = sections[:]

    with ThreadPoolExecutor(max_workers=3) as executor:
        futures = {}
        for name, _ in sections_to_write:
            if _cancelled():
                break
            thesis = section_theses.get(name, "")
            _progress("build_agent_started", {"stage": "build_agent_started", "agent": f"writer:{name}", "model": _MODEL_WRITER})
            fut = executor.submit(
                _run_section_writer,
                client, question, type_id, name, thesis,
                combined_research,
                "", raw_notes_context, _level,
            )
            futures[fut] = name

        for fut in as_completed(futures):
            sec_name, body = fut.result()
            section_bodies[sec_name] = body
            _progress("build_agent_completed", {
                "stage": "build_agent_completed",
                "agent": f"writer:{sec_name}",
                "output_chars": len(body),
            })

    # Preserve section order from template
    ordered_sections = [(name, section_bodies.get(name, "")) for name, _ in sections]

    # ------------------------------------------------------------------
    # Step 3: Critic
    # ------------------------------------------------------------------
    if _cancelled():
        assembled_pre_critic = "\n\n".join(f"## {n}\n\n{b}" for n, b in ordered_sections if b)
        return {"ok": False, "message": "Cancelled before critic.", "body": assembled_pre_critic}

    assembled_draft = "\n\n".join(f"## {n}\n\n{b}" for n, b in ordered_sections if b)
    _progress("build_agent_started", {"stage": "build_agent_started", "agent": "critic", "model": _MODEL_CRITIC})
    critic_output = _run_critic(client, assembled_draft, type_id, question, raw_notes_context, _level, research_context)
    _progress("build_agent_completed", {"stage": "build_agent_completed", "agent": "critic", "output_chars": len(critic_output)})

    # ------------------------------------------------------------------
    # Step 4: Revisor (targeted — only flagged sections)
    # ------------------------------------------------------------------
    critic_notes = _parse_critic_notes(critic_output, section_names)
    revised_sections = list(ordered_sections)

    if critic_notes and not _cancelled():
        _progress("essay_revision_started", {"flagged_sections": list(critic_notes.keys())})
        for idx, (name, body) in enumerate(revised_sections):
            if name in critic_notes and not _cancelled():
                _progress("build_agent_started", {"stage": "build_agent_started", "agent": f"revisor:{name}", "model": _MODEL_WRITER})
                revised_body = _run_revisor(client, name, body, critic_notes[name], type_id, question, combined_research)
                revised_sections[idx] = (name, revised_body)
                _progress("build_agent_completed", {"stage": "build_agent_completed", "agent": f"revisor:{name}", "output_chars": len(revised_body)})

    # ------------------------------------------------------------------
    # Step 5: Compositor
    # ------------------------------------------------------------------
    if _cancelled():
        fallback = "\n\n".join(f"## {n}\n\n{b}" for n, b in revised_sections if b)
        return {"ok": False, "message": "Cancelled before compositor.", "body": fallback}

    _progress("build_agent_started", {"stage": "build_agent_started", "agent": "compositor", "model": _MODEL_COMPOSITOR})
    final_body = _run_compositor(client, revised_sections, type_id, question, combined_research)
    _progress("build_agent_completed", {"stage": "build_agent_completed", "agent": "compositor", "output_chars": len(final_body)})

    warning_banner = ""
    longform_lane_cfg = lane_model_config(repo_root, "make_longform")
    longform_policy = (
        longform_lane_cfg.get("escalation_policy", {})
        if isinstance(longform_lane_cfg.get("escalation_policy", {}), dict)
        else {}
    )
    if bool(longform_policy.get("enabled", False)) and not _cancelled():
        importance = "high" if type_id in {"essay_long", "video_script", "newsletter"} else "medium"

        def _merge_tier_for_critic(tier_cfg: dict[str, Any]) -> dict[str, Any]:
            merged = dict(longform_lane_cfg)
            if isinstance(tier_cfg, dict):
                merged.update(tier_cfg)
            if "synthesis_fallback_models" not in merged and isinstance(merged.get("fallback_models", []), list):
                merged["synthesis_fallback_models"] = list(merged.get("fallback_models", []))
            return merged

        _progress("skeptic_pass_started", {"phase": "longform_loop", "note": "Running longform critique/revise loop."})
        loop_result = run_draft_critique_revise(
            repo_root=repo_root,
            lane_key="make_longform",
            draft_fn=lambda _tier_cfg: final_body,
            critique_fn=lambda draft_text, tier_cfg: run_skeptic_pass_with_severity(
                question,
                draft_text,
                client=client,
                model_cfg=_merge_tier_for_critic(tier_cfg),
                findings=None,
            ),
            importance=importance,
            client=client,
            telemetry_ctx={
                "task_class": "make_longform",
                "project_slug": project_slug,
                "type_id": type_id,
            },
            cancel_checker=cancel_checker,
        )
        final_body = str(loop_result.final_text or "").strip() or final_body
        if loop_result.critique_logs:
            critic_output = "\n\n".join(
                str(item).strip() for item in loop_result.critique_logs if str(item).strip()
            )
        warning_banner = str(loop_result.warning_banner or "").strip()
        if warning_banner:
            final_body = f"**Warning:** {warning_banner}\n\n{final_body}"
        _progress(
            "skeptic_pass_completed",
            {
                "phase": "longform_loop",
                "critique_chars": len(str(critic_output or "").strip()),
                "premium_activated": bool(loop_result.premium_activated),
            },
        )

    # ------------------------------------------------------------------
    # Step 6: Quality gate
    # ------------------------------------------------------------------
    passed, gate_issues = _quality_gate(final_body, type_id)
    if not passed:
        _progress("build_quality_gate_failed", {"issues": gate_issues})
        # Auto-fix: try one more compositor pass with explicit fix instructions
        try:
            fix_prompt = (
                f"The following issues were detected:\n" +
                "\n".join(f"- {i}" for i in gate_issues) +
                f"\n\nPlease fix these issues in the document below and return the corrected version:\n\n{_trim(final_body, 12000)}"
            )
            fix_result = chat_with_self_fix_retry(
                client,
                model=_MODEL_COMPOSITOR,
                system_prompt=f"You are a {type_id.replace('_', ' ')} editor. Fix the issues listed. Return the complete corrected document.",
                user_prompt=fix_prompt,
                temperature=0.2,
                num_ctx=24576,
                think=False,
                timeout=300,
                retry_attempts=2,
                retry_backoff_sec=1.5,
                max_self_fix_attempts=3,
                validator=lambda candidate: "\n".join(_quality_gate(candidate, type_id)[1]) or None,
            )
            fixed = str(fix_result.text or "").strip()
            if fixed and len(fixed) > len(final_body) * 0.8:
                final_body = fixed
                passed, gate_issues = _quality_gate(final_body, type_id)
        except Exception:
            pass
    else:
        _progress("build_quality_gate_passed", {})

    bus.emit("longform_pool", "completed", {
        "project": project_slug,
        "type_id": type_id,
        "chars": len(final_body),
        "sections_written": len([b for _, b in revised_sections if b]),
    })

    return {
        "ok": True,
        "body": final_body,
        "sections_written": [n for n, b in revised_sections if b],
        "critic_notes": critic_output,
        "quality_gate_passed": passed,
        "quality_gate_issues": gate_issues,
        "warning_banner": warning_banner,
        "message": f"{type_id.replace('_', ' ').title()} complete — {len(final_body):,} chars.",
    }
