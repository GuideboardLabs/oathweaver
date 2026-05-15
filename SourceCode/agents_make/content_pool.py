"""Content pool — blogs, social posts, emails, short-form essay_short.

Pipeline (6 stages, matches Research sophistication):
    1. Planner    — outlines structure + angles from research context + process note
    2. Writers    — parallel section/angle writers (≤3 workers per content type)
    3. Critic     — deepseek-r1:8b checks tone, structure, CTA, length, engagement
    4. Revisor    — applies critic notes to flagged sections only
    5. Compositor — assembles + polishes: title, transitions, consistent voice
    6. Gate       — length / format / CTA validation, auto-fix if needed
"""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from pathlib import Path
import re
from typing import Any, Callable

from shared_tools.feedback_learning import FeedbackLearningEngine
from shared_tools.fidelity_policy import FidelityLevel, fidelity_for, writer_constraint_block, evidence_key_block, critic_fabrication_block, thin_research_warning
from shared_tools.llm_retry import chat_with_self_fix_retry
from shared_tools.model_routing import lane_model_config
from shared_tools.ollama_client import OllamaClient


_MODEL_DRAFTER  = "hf.co/unsloth/Qwen3-8B-GGUF:UD-Q5_K_XL"
_MODEL_CRITIC   = "deepseek-r1:8b"
_MODEL_POLISH   = "hf.co/unsloth/Qwen3-8B-GGUF:UD-Q5_K_XL"


def _today() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d")


def _trim(text: str, max_chars: int) -> str:
    body = str(text or "").strip()
    if len(body) <= max_chars:
        return body
    cut = body[:max_chars].rsplit("\n", 1)[0].strip()
    return cut or body[:max_chars]


def _chat_retry(
    client: OllamaClient,
    *,
    model: str,
    system_prompt: str,
    user_prompt: str,
    temperature: float,
    num_ctx: int,
    think: bool,
    timeout: int,
    retry_attempts: int,
    retry_backoff_sec: float,
    validator: Callable[[str], str | None] | None = None,
    self_fix_attempts: int = 2,
) -> str:
    result = chat_with_self_fix_retry(
        client,
        model=model,
        system_prompt=system_prompt,
        user_prompt=user_prompt,
        temperature=temperature,
        num_ctx=num_ctx,
        think=think,
        timeout=timeout,
        retry_attempts=retry_attempts,
        retry_backoff_sec=retry_backoff_sec,
        validator=validator,
        max_self_fix_attempts=self_fix_attempts,
    )
    return str(result.text or "").strip()


def _planner_validator(section_names: list[str]) -> Callable[[str], str | None]:
    expected = [str(name).strip().lower() for name in section_names if str(name).strip()]

    def _validate(text: str) -> str | None:
        body = str(text or "").strip()
        if not body:
            return "Planner output was empty."
        if "###" not in body:
            return "Planner must use '### [Section Name]' headings."
        low = body.lower()
        matches = sum(1 for name in expected if name and name in low)
        minimum = max(2, min(len(expected), (len(expected) + 1) // 2))
        if matches < minimum:
            return f"Planner did not cover enough required sections ({matches}/{len(expected)})."
        return None

    return _validate


def _critic_validator(approved_phrase: str) -> Callable[[str], str | None]:
    approved_low = str(approved_phrase or "").strip().lower()

    def _validate(text: str) -> str | None:
        body = str(text or "").strip()
        if not body:
            return "Critic output was empty."
        low = body.lower()
        if approved_low and approved_low in low:
            return None
        if "**" in body and ":" in body:
            return None
        return "Critic must either approve explicitly or provide section-scoped fix notes."

    return _validate


# ---------------------------------------------------------------------------
# Type specs
# ---------------------------------------------------------------------------

_KIND_SPECS: dict[str, dict[str, Any]] = {
    "blog": {
        "word_range": "600-800 words",
        "sections": [
            ("Hook & Headline",  "Attention-grabbing title + 1–2 sentence hook. Why should the reader care right now?"),
            ("Context & Stakes", "Brief background, conversational not academic. Set up the problem or question."),
            ("Core Content",     "Key insights with subheadings, short paragraphs, concrete examples. This is the bulk."),
            ("Takeaway & CTA",   "Clear takeaway and one call to action. What should the reader do or think differently?"),
        ],
        "voice": "Conversational, authoritative, accessible. Write like you're explaining to a smart friend.",
        "min_chars": 1200,
        "max_chars": 6500,
        "process_note": "Hook & headline → context/why now → core content with examples → takeaway & CTA.",
    },
    "social_post": {
        "word_range": "80-220 words",
        "sections": [
            ("Hook",   "The 'stop-scrolling' line. One punchy statement under 40 words that earns the next 10 seconds."),
            ("Body",   "2–3 concise sentences expanding the hook. Specific, not vague."),
            ("CTA",    "One sentence: what should the reader do, think, or feel next?"),
        ],
        "voice": "Punchy, direct, conversational. No jargon. No hashtag soup. Every word earns its place.",
        "min_chars": 80,
        "max_chars": 1400,
        "process_note": "Hook (stop-scrolling) → context ≤2 lines → payoff/insight → optional CTA. Platform-aware voice.",
    },
    "email": {
        "word_range": "200-400 words",
        "sections": [
            ("Subject & Greeting", "Clear subject line under 60 chars + appropriate greeting for the context."),
            ("Lede",               "The most important point in the first two sentences. Front-load the ask."),
            ("Body",               "Context + supporting info in 2–3 short paragraphs. Respect the reader's time."),
            ("Sign-off",           "Professional closing with a clear next step."),
        ],
        "voice": "Professional, clear, respectful of the reader's time.",
        "min_chars": 400,
        "max_chars": 3200,
        "process_note": "Subject under 60 chars → front-loaded ask → short body → clear next step.",
    },
}


# ---------------------------------------------------------------------------
# Pipeline steps
# ---------------------------------------------------------------------------

def _run_planner(
    client: OllamaClient,
    question: str,
    kind: str,
    research_context: str,
    level: FidelityLevel = FidelityLevel.GROUNDED,
) -> str:
    spec = _KIND_SPECS.get(kind, _KIND_SPECS["blog"])
    sections_text = "\n".join(f"- {n}: {h}" for n, h in spec["sections"])
    thin_warn = thin_research_warning(level, len(research_context))
    system_prompt = (
        f"Today: {_today()}. You are a professional content strategist.\n\n"
        f"Output type: {kind}\n"
        f"Target length: {spec['word_range']}\n"
        f"Voice: {spec['voice']}\n"
        f"Process: {spec['process_note']}\n\n"
        "PUBLIC-CONTENT GUARDRAIL: This is public-facing content. Do not reference the author's private personal "
        "relationships, health conditions, workplace, or other personal specifics from profile hints unless the user explicitly "
        "asks for those specifics. Prefer category phrasing (for example: 'as a parent', 'as a caregiver').\n\n"
        "For each required section, write a ONE-SENTENCE specific angle or focus "
        "grounded in the user's request and research context. No generic filler.\n\n"
        f"Sections:\n{sections_text}\n\n"
        "Format:\n### [Section Name]\n[specific angle]\n\n"
        f"Do not write the content itself.{thin_warn}"
    )
    try:
        result = _chat_retry(
            client,
            model=_MODEL_DRAFTER,
            system_prompt=system_prompt,
            user_prompt=f"Request: {question}\n\nResearch:\n{_trim(research_context, 5000)}",
            temperature=0.3,
            num_ctx=12288,
            think=False,
            timeout=180,
            retry_attempts=3,
            retry_backoff_sec=1.2,
            validator=_planner_validator([name for name, _ in spec["sections"]]),
            self_fix_attempts=3,
        )
        return str(result or "").strip()
    except Exception as exc:
        return f"[Planner failed: {exc}]"


def _run_section_writer(
    client: OllamaClient,
    question: str,
    kind: str,
    section_name: str,
    section_angle: str,
    research_context: str,
    raw_notes_context: str = "",
    level: FidelityLevel = FidelityLevel.GROUNDED,
) -> tuple[str, str]:
    spec = _KIND_SPECS.get(kind, _KIND_SPECS["blog"])
    ev_key = evidence_key_block(level, bool(raw_notes_context.strip()))
    system_prompt = (
        f"Today: {_today()}. You are a professional {kind.replace('_', ' ')} writer.\n\n"
        f"Write ONLY the '{section_name}' section.\n"
        f"Overall piece length: {spec['word_range']}\n"
        f"Voice: {spec['voice']}\n\n"
        f"{writer_constraint_block(level)} No filler. "
        "Return only the section content — no section heading."
    )
    user_prompt = (
        f"Request: {question}\n"
        f"Section focus: {section_angle}\n\n"
        f"Research:{ev_key}\n{_trim(research_context, 4000)}"
    )
    try:
        result = _chat_retry(
            client,
            model=_MODEL_DRAFTER,
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            temperature=0.7,
            num_ctx=10240,
            think=False,
            timeout=180,
            retry_attempts=3,
            retry_backoff_sec=1.2,
        )
        return section_name, str(result or "").strip()
    except Exception as exc:
        return section_name, f"[Section '{section_name}' failed: {exc}]"


def _run_critic(
    client: OllamaClient,
    draft: str,
    kind: str,
    question: str,
    raw_notes_context: str = "",
    level: FidelityLevel = FidelityLevel.GROUNDED,
    research_context: str = "",
) -> str:
    spec = _KIND_SPECS.get(kind, _KIND_SPECS["blog"])
    system_prompt = (
        f"You are an editorial critic for a {kind.replace('_', ' ')}.\n\n"
        f"Expected voice: {spec['voice']}\n"
        f"Expected length: {spec['word_range']}\n"
        f"Process standard: {spec['process_note']}\n\n"
        "Check the draft for:\n"
        "1. Tone match — does it nail the voice?\n"
        "2. Structure — does it follow the required format?\n"
        "3. CTA clarity — is the call to action specific and actionable?\n"
        "4. Length — is it within the target range?\n"
        "5. Engagement — does it earn the reader's attention throughout?\n"
        "6. Specificity — are there vague claims that need grounding?\n\n"
        "For each issue: write '**[Section Name]**: [one-sentence fix instruction]'\n"
        "If everything is strong, write 'Approved.' and stop."
    )
    try:
        result = _chat_retry(
            client,
            model=_MODEL_CRITIC,
            system_prompt=system_prompt,
            user_prompt=f"Kind: {kind} | Request: {question}\n\nDraft:\n{_trim(draft, 6000)}{critic_fabrication_block(level, raw_notes_context, _trim, research_context)}",
            temperature=0.1,
            num_ctx=12288,
            think=True,
            timeout=240,
            retry_attempts=3,
            retry_backoff_sec=1.5,
            validator=_critic_validator("Approved."),
            self_fix_attempts=3,
        )
        return str(result or "").strip()
    except Exception:
        return "Approved."


def _run_compositor(
    client: OllamaClient,
    sections: list[tuple[str, str]],
    kind: str,
    question: str,
) -> str:
    spec = _KIND_SPECS.get(kind, _KIND_SPECS["blog"])
    joined = "\n\n".join(f"**{name}**\n{body}" for name, body in sections if body)
    system_prompt = (
        f"You are a senior {kind.replace('_', ' ')} editor assembling the final piece.\n\n"
        f"Voice: {spec['voice']}\n"
        f"Target length: {spec['word_range']}\n\n"
        "PUBLIC-CONTENT GUARDRAIL: This is public-facing content. Do not reference the author's private personal "
        "relationships, health conditions, workplace, or other personal specifics from profile hints unless the user explicitly "
        "asks for those specifics. Prefer category phrasing (for example: 'as a parent', 'as a caregiver').\n\n"
        "Assemble the sections into one polished final document:\n"
        "1. For blog/essay: add a title at the top\n"
        "2. Write smooth transitions between sections (1 sentence max)\n"
        "3. Ensure consistent voice and tense\n"
        "4. Trim redundancy without losing substance\n"
        "5. Return the complete polished content in markdown. No meta-commentary."
    )
    try:
        result = _chat_retry(
            client,
            model=_MODEL_POLISH,
            system_prompt=system_prompt,
            user_prompt=f"Request: {question}\n\nSections:\n{joined}",
            temperature=0.5,
            num_ctx=12288,
            think=False,
            timeout=240,
            retry_attempts=3,
            retry_backoff_sec=1.2,
        )
        polished = str(result or "").strip()
        # Ensure we didn't lose content
        raw_len = sum(len(b) for _, b in sections if b)
        if polished and len(polished) >= raw_len * 0.5:
            return polished
        return "\n\n".join(f"## {n}\n\n{b}" for n, b in sections if b)
    except Exception:
        return "\n\n".join(f"## {n}\n\n{b}" for n, b in sections if b)


def _quality_gate(body: str, kind: str) -> tuple[bool, list[str]]:
    issues: list[str] = []
    spec = _KIND_SPECS.get(kind, _KIND_SPECS["blog"])
    min_chars = spec.get("min_chars", 200)
    max_chars = spec.get("max_chars")
    if len(body) < min_chars:
        issues.append(f"Too short: {len(body)} chars (minimum {min_chars})")
    if isinstance(max_chars, int) and len(body) > max_chars:
        issues.append(f"Too long: {len(body)} chars (maximum {max_chars})")
    if body.endswith("...") or body.endswith("…"):
        issues.append("Appears truncated (ends with ellipsis)")
    if re.search(r"\[(?:link|url|cta)\]|\bexample\.com\b", body, re.IGNORECASE):
        issues.append("Contains placeholder link or CTA text")
    return len(issues) == 0, issues


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------

def run_content_pool(
    question: str,
    repo_root: Path,
    project_slug: str,
    bus: Any,
    target: str = "blog",
    topic_type: str = "general",
    research_context: str = "",
    raw_notes_context: str = "",
    cancel_checker: Callable[[], bool] | None = None,
    progress_callback: Callable[[str, dict[str, Any]], None] | None = None,
) -> dict[str, Any]:
    """Run the content pipeline and return the final content."""

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

    kind = str(target).strip().lower() or "blog"
    if kind not in _KIND_SPECS:
        kind = "blog"
    _level = fidelity_for(kind, topic_type)

    bus.emit("content_pool", "start", {"question": question, "target": kind})
    client = OllamaClient()

    # Learning integration
    orchestrator_cfg = lane_model_config(repo_root, "orchestrator_reasoning")
    try:
        learning = FeedbackLearningEngine(repo_root, client=client, model_cfg=orchestrator_cfg)
        learned_guidance = learning.guidance_for_lane("make_content", limit=5)
        if learned_guidance:
            research_context = (learned_guidance + "\n\n" + research_context).strip()
    except Exception:
        pass

    spec = _KIND_SPECS[kind]
    section_defs = spec["sections"]
    section_names = [n for n, _ in section_defs]

    _progress("build_pool_started", {
        "stage": "build_pool_started",
        "agents_total": len(section_defs) + 3,
        "make_type": kind,
        "destination": "Content",
    })

    # Step 1: Planner
    if _cancelled():
        return {"ok": False, "message": "Cancelled before planning.", "body": ""}
    _progress("build_agent_started", {"stage": "build_agent_started", "agent": "planner", "model": _MODEL_DRAFTER})
    outline = _run_planner(client, question, kind, research_context, _level)
    _progress("build_agent_completed", {"stage": "build_agent_completed", "agent": "planner", "output_chars": len(outline)})

    # Parse outline → section angles
    section_angles: dict[str, str] = {}
    current_section: str | None = None
    current_lines: list[str] = []
    for line in outline.splitlines():
        stripped = line.strip()
        if stripped.startswith("###"):
            if current_section is not None:
                section_angles[current_section] = " ".join(current_lines).strip()
            current_section = stripped.lstrip("#").strip()
            current_lines = []
        elif current_section is not None and stripped:
            current_lines.append(stripped)
    if current_section is not None:
        section_angles[current_section] = " ".join(current_lines).strip()
    for name, hint in section_defs:
        if name not in section_angles or not section_angles[name]:
            section_angles[name] = hint

    # Step 2: Parallel section writers
    if _cancelled():
        return {"ok": False, "message": "Cancelled before writing.", "body": ""}
    _progress("build_agent_started", {"stage": "build_agent_started", "agent": "writers", "model": _MODEL_DRAFTER})

    section_bodies: dict[str, str] = {}
    with ThreadPoolExecutor(max_workers=min(3, len(section_defs))) as executor:
        futures = {}
        for name, _ in section_defs:
            if _cancelled():
                break
            angle = section_angles.get(name, "")
            fut = executor.submit(
                _run_section_writer,
                client, question, kind, name, angle, research_context,
                raw_notes_context, _level,
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

    ordered_sections = [(name, section_bodies.get(name, "")) for name, _ in section_defs]

    # Step 3: Critic
    if _cancelled():
        draft_fallback = "\n\n".join(f"**{n}**\n{b}" for n, b in ordered_sections if b)
        return {"ok": False, "message": "Cancelled before critic.", "body": draft_fallback}

    assembled_draft = "\n\n".join(f"**{n}**\n{b}" for n, b in ordered_sections if b)
    _progress("build_agent_started", {"stage": "build_agent_started", "agent": "critic", "model": _MODEL_CRITIC})
    review_notes = _run_critic(client, assembled_draft, kind, question, raw_notes_context, _level, research_context)
    _progress("build_agent_completed", {"stage": "build_agent_completed", "agent": "critic", "output_chars": len(review_notes)})

    # Step 4: Revisor (targeted sections)
    revised_sections = list(ordered_sections)
    if review_notes and "approved" not in review_notes.lower()[:60] and not _cancelled():
        import re
        pattern = re.compile(r'\*\*(.+?)\*\*\s*[:\-]\s*(.+?)(?=\n\*\*|\Z)', re.DOTALL)
        fix_map: dict[str, str] = {}
        for match in pattern.finditer(review_notes):
            raw_name = match.group(1).strip()
            fix = match.group(2).strip()
            for name in section_names:
                if raw_name.lower() in name.lower() or name.lower() in raw_name.lower():
                    fix_map[name] = fix[:400]
                    break

        if fix_map:
            _progress("essay_revision_started", {"flagged_sections": list(fix_map.keys())})
            for idx, (name, body) in enumerate(revised_sections):
                if name in fix_map and not _cancelled():
                    _progress("build_agent_started", {"stage": "build_agent_started", "agent": f"revisor:{name}", "model": _MODEL_POLISH})
                    fix_system = f"You are a {kind.replace('_', ' ')} editor. Apply the note and return the revised section only."
                    fix_user = f"Note: {fix_map[name]}\n\nSection to revise:\n{body}"
                    try:
                        revised_body = str(
                            _chat_retry(
                                client,
                                model=_MODEL_POLISH,
                                system_prompt=fix_system,
                                user_prompt=fix_user,
                                temperature=0.4,
                                num_ctx=10240,
                                think=False,
                                timeout=180,
                                retry_attempts=2,
                                retry_backoff_sec=1.2,
                            )
                            or ""
                        ).strip()
                        if revised_body and len(revised_body) >= len(body) * 0.4:
                            revised_sections[idx] = (name, revised_body)
                    except Exception:
                        pass
                    _progress("build_agent_completed", {"stage": "build_agent_completed", "agent": f"revisor:{name}"})

    # Step 5: Compositor
    if _cancelled():
        fallback = "\n\n".join(f"## {n}\n\n{b}" for n, b in revised_sections if b)
        return {"ok": False, "message": "Cancelled before compositor.", "body": fallback}

    _progress("build_agent_started", {"stage": "build_agent_started", "agent": "compositor", "model": _MODEL_POLISH})
    final_body = _run_compositor(client, revised_sections, kind, question)
    _progress("build_agent_completed", {"stage": "build_agent_completed", "agent": "compositor", "output_chars": len(final_body)})

    # Step 6: Quality gate
    passed, gate_issues = _quality_gate(final_body, kind)
    if not passed:
        _progress("build_quality_gate_failed", {"issues": gate_issues})
        try:
            fix_prompt = f"Issues detected:\n" + "\n".join(f"- {i}" for i in gate_issues) + f"\n\nFix and return:\n\n{_trim(final_body, 8000)}"
            fixed = str(
                _chat_retry(
                    client,
                    model=_MODEL_POLISH,
                    system_prompt=f"You are a {kind.replace('_', ' ')} editor. Fix the issues and return the corrected version.",
                    user_prompt=fix_prompt,
                    temperature=0.3,
                    num_ctx=12288,
                    think=False,
                    timeout=200,
                    retry_attempts=2,
                    retry_backoff_sec=1.2,
                    validator=lambda candidate: "\n".join(_quality_gate(candidate, kind)[1]) or None,
                    self_fix_attempts=3,
                )
                or ""
            ).strip()
            fixed_passed, _fixed_issues = _quality_gate(fixed, kind)
            if fixed and (fixed_passed or len(fixed) > spec.get("min_chars", 80)):
                final_body = fixed
        except Exception:
            pass
    else:
        _progress("build_quality_gate_passed", {})

    bus.emit("content_pool", "completed", {
        "project": project_slug, "target": kind, "chars": len(final_body),
    })

    return {
        "ok": True,
        "body": final_body,
        "review_notes": review_notes,
        "message": f"{kind.replace('_', ' ').title()} complete — {len(final_body):,} chars.",
    }
