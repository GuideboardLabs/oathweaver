"""Specialist pool — domain-expert deliverables for medical, finance, sports, history, game design.

Pipeline:
    1. Research Integration — reads all project research context
    2. Outline             — hf.co/unsloth/Qwen3-8B-GGUF:UD-Q5_K_XL uses domain-specific section templates
    3. Section Writer      — hf.co/unsloth/Qwen3-8B-GGUF:UD-Q5_K_XL writes sections in parallel (max 3)
    4. Domain Critic       — deepseek-r1:8b (think mode) validates domain-specific requirements
    5. Revision Pass       — hf.co/unsloth/Qwen3-8B-GGUF:UD-Q5_K_XL applies critic notes
    6. Compositor          — hf.co/unsloth/Qwen3-8B-GGUF:UD-Q5_K_XL assembles final document
    7. Quality Gate        — validates length, disclaimers, truncation

Reuses section templates from essay_pool for domain-specific structure.
"""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

from core.output_contracts import OutputContract, OutputContractAuditor
from shared_tools.fidelity_policy import FidelityLevel, writer_constraint_block, evidence_key_block, critic_fabrication_block, thin_research_warning
from shared_tools.llm_retry import chat_with_self_fix_retry
from shared_tools.ollama_client import OllamaClient


_MODEL_OUTLINE    = "hf.co/unsloth/Qwen3-8B-GGUF:UD-Q5_K_XL"
_MODEL_WRITER     = "hf.co/unsloth/Qwen3-8B-GGUF:UD-Q5_K_XL"
_MODEL_CRITIC     = "deepseek-r1:8b"
_MODEL_COMPOSITOR = "hf.co/unsloth/Qwen3-8B-GGUF:UD-Q5_K_XL"
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
# Domain section templates (specialized versions)
# ---------------------------------------------------------------------------

_SECTIONS_MEDICAL = [
    ("Clinical Summary",        "The condition, intervention, or topic in plain language. Who this affects and why it matters."),
    ("Evidence Review",         "Peer-reviewed findings by evidence tier: RCT > observational > case study > expert opinion."),
    ("Risk & Safety Profile",   "Adverse events, contraindications, drug interactions, population-specific risks."),
    ("Clinical Guidelines",     "Current WHO/CDC/NIH/specialty society recommendations and their evidence basis."),
    ("Patient Considerations",  "Practical implications. Questions a patient should bring to a clinician."),
    ("Limitations & Caveats",   "This is not medical advice. Evidence gaps, study limitations, jurisdiction differences."),
]

_SECTIONS_FINANCE = [
    ("Executive Summary",       "Investment thesis or market position in 3-5 sentences. Bottom line up front."),
    ("Market Context",          "Macro environment, sector dynamics, conditions framing the analysis."),
    ("Core Findings",           "Specific data points, valuations, trend analysis. Cite figures with sources and dates."),
    ("Risk Factors",            "Downside scenarios, tail risks, liquidity constraints, regulatory headwinds."),
    ("Thesis & Recommendation", "Actionable position with confidence level and key assumptions stated explicitly."),
    ("Caveats & Disclosures",   "Uncertainty disclosures, what would change the recommendation, timeline dependencies."),
]

_SECTIONS_SPORTS = [
    ("Introduction & Stakes",       "What event or matchup this analyzes and why it matters."),
    ("Context & Current Form",      "Standings, recent results, roster state, scheduling notes."),
    ("Statistical Analysis",        "Head-to-head records, key performance metrics, historical trajectory."),
    ("Risk & Uncertainty Factors",  "Injuries, roster changes, officiating, venue, momentum."),
    ("Analysis & Outlook",          "Synthesis into a coherent assessment of what is most likely and why."),
    ("Conclusion",                  "Key takeaways and remaining open questions."),
]

_SECTIONS_HISTORY = [
    ("Introduction & Thesis",       "The historical question, time period, and central argument."),
    ("Historical Background",       "Political, social, economic conditions. Specific dates and actors."),
    ("Key Events & Turning Points", "Pivotal events in sequence. Causation vs. correlation."),
    ("Key Actors & Motivations",    "Agents of change: who acted, what they wanted, why they succeeded or failed."),
    ("Historiographical Debate",    "Competing scholarly interpretations. Schools of thought."),
    ("Conclusion & Legacy",         "Synthesis. Precedents set for later events."),
]

_SECTIONS_GAME_DESIGN = [
    ("Game Overview",           "Title, genre, platform, target audience, core fantasy in 2-3 sentences."),
    ("Core Loop",               "The minute-to-minute gameplay loop. What the player does most. Why it's satisfying."),
    ("Systems Design",          "Progression, economy, combat/interaction systems. How they interlock."),
    ("Content & Narrative",     "World, story hooks, mission/quest structure, procedural vs. handcrafted content."),
    ("Technical Constraints",   "Platform requirements, scope feasibility, known technical risks."),
    ("Production Notes",        "Milestones, team size assumptions, MVP scope vs. full vision."),
]

_DOMAIN_SECTIONS: dict[str, list[tuple[str, str]]] = {
    "medical":         _SECTIONS_MEDICAL,
    "finance":         _SECTIONS_FINANCE,
    "sports":          _SECTIONS_SPORTS,
    "history":         _SECTIONS_HISTORY,
    "game_design_doc": _SECTIONS_GAME_DESIGN,
}


# Domain-specific critic instructions
_DOMAIN_CRITIC_INSTRUCTIONS: dict[str, str] = {
    "medical": (
        "Validate:\n"
        "- Evidence tiers are correctly labeled (RCT, observational, case study, expert opinion)\n"
        "- Safety disclaimers are present and prominent\n"
        "- No diagnostic language (do not diagnose, prescribe, or recommend specific treatments)\n"
        "- Black box warnings and contraindications are included where applicable\n"
        "- 'This is not medical advice' disclaimer is present in caveats section"
    ),
    "finance": (
        "Validate:\n"
        "- Risk disclosures are specific, not generic boilerplate\n"
        "- Assumptions are explicitly stated and testable\n"
        "- No specific investment advice without caveats\n"
        "- Data sources and dates are cited\n"
        "- 'This is not financial advice' disclaimer is present"
    ),
    "sports": (
        "Validate:\n"
        "- Statistical claims have specific figures, not vague assertions\n"
        "- Recency of data is noted (as of [date])\n"
        "- Injury/roster information includes freshness caveats\n"
        "- Analysis accounts for sample size and context"
    ),
    "history": (
        "Validate:\n"
        "- Source quality is noted (primary vs. secondary, contemporary vs. retrospective)\n"
        "- Historiographical balance — competing interpretations are represented\n"
        "- No anachronisms (applying modern concepts to past events without flagging)\n"
        "- Dates and actors are specific, not vague"
    ),
    "game_design_doc": (
        "Validate:\n"
        "- Core loop is clearly defined and sounds engaging\n"
        "- Systems interlock coherently (economy feeds progression, etc.)\n"
        "- Scope is feasible for stated team/timeline\n"
        "- Technical constraints are realistic\n"
        "- MVP scope is clearly distinguished from full vision"
    ),
}


# ---------------------------------------------------------------------------
# Quality gate
# ---------------------------------------------------------------------------

def _quality_gate(body: str, kind: str) -> tuple[bool, list[str]]:
    issues: list[str] = []
    min_lengths = {
        "medical": 1500, "finance": 1500, "sports": 1200,
        "history": 1500, "game_design_doc": 2000,
    }
    min_len = min_lengths.get(kind, 1000)
    if len(body) < min_len:
        issues.append(f"Body too short: {len(body)} chars, expected >= {min_len}")

    low = body.lower()
    if kind == "medical" and "not medical advice" not in low:
        issues.append("Missing medical disclaimer")
    if kind == "finance" and "not financial advice" not in low:
        issues.append("Missing financial disclaimer")

    if body.rstrip().endswith(("...", "\u2026")):
        issues.append("Possible truncation detected (ends with ellipsis)")

    return (len(issues) == 0, issues)


# ---------------------------------------------------------------------------
# Pipeline steps
# ---------------------------------------------------------------------------

def _run_outline(
    client: OllamaClient,
    question: str,
    sections: list[tuple[str, str]],
    research_context: str,
    raw_notes_context: str,
    kind: str,
) -> str:
    section_list = "\n".join(f"  {i+1}. {name}: {hint}" for i, (name, hint) in enumerate(sections))
    thin_warn = thin_research_warning(FidelityLevel.STRICT, len(research_context))
    system_prompt = (
        f"Today: {_today()}. "
        f"You are a domain expert outliner for a {kind.replace('_', ' ')} deliverable. "
        "Given research context and a writing request, produce a tight outline: "
        "one thesis sentence per section grounded in the research. "
        "Use facts, figures, and names from the research only — not from your training knowledge, "
        "which may be inaccurate for domain-specific details. "
        f"Output each section as: '### [Section Name]\\n[1-2 sentence thesis]'. Nothing else."
        f"{thin_warn}"
    )
    user_prompt = (
        f"Domain: {kind} | Request: {question}\n\n"
        f"Sections to plan:\n{section_list}\n\n"
        f"Research context:\n{_trim(research_context, 12000)}\n\n"
        f"Raw research notes:\n{_trim(raw_notes_context, 6000)}\n\n"
        "Focus on the literal request and supplied research only."
    )
    try:
        result = chat_with_self_fix_retry(
            client,
            model=_MODEL_OUTLINE,
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            temperature=0.2,
            num_ctx=24576,
            think=False,
            timeout=300,
            retry_attempts=4,
            retry_backoff_sec=1.5,
            validator=_contract_validator(
                stage="specialist_outline",
                required_markers=("###",),
                min_chars=100,
            ),
        )
        return str(result.text or "").strip()
    except Exception:
        return "\n".join(f"### {name}\n{hint}" for name, hint in sections)


def _run_section_writer(
    client: OllamaClient,
    section_name: str,
    section_thesis: str,
    outline: str,
    question: str,
    research_context: str,
    kind: str,
    sources_context: str = "",
    raw_notes_context: str = "",
) -> str:
    ev_key = evidence_key_block(FidelityLevel.STRICT, bool(raw_notes_context.strip()))
    system_prompt = (
        f"Today: {_today()}. "
        f"You are a domain expert writer for a {kind.replace('_', ' ')} deliverable. "
        "Write ONE section only — approximately 400-500 words. "
        f"{writer_constraint_block(FidelityLevel.STRICT)} "
        "Cite sources where available. Be precise with data, dates, and figures. "
        "Do not start with the section title — the compositor handles headers."
    )
    sources_block = f"\n\nSources:\n{_trim(sources_context, 4000)}" if sources_context.strip() else ""
    user_prompt = (
        f"Full outline (write ONLY your assigned section):\n{_trim(outline, 2000)}\n\n"
        f"YOUR SECTION: {section_name}\n"
        f"Thesis: {section_thesis}\n\n"
        f"Research context:{ev_key}\n{_trim(research_context, 10000)}\n\n"
        f"Request: {question}"
        f"{sources_block}"
    )
    try:
        result = chat_with_self_fix_retry(
            client,
            model=_MODEL_WRITER,
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            temperature=0.2,
            num_ctx=20480,
            think=False,
            timeout=300,
            retry_attempts=4,
            retry_backoff_sec=1.5,
            validator=_contract_validator(
                stage="specialist_section_writer",
                min_chars=220,
            ),
        )
        return str(result.text or "").strip()
    except Exception as exc:
        return f"[Section generation failed: {exc}]"


def _run_domain_critic(
    client: OllamaClient,
    sections_text: str,
    question: str,
    kind: str,
    raw_notes_context: str = "",
    research_context: str = "",
) -> str:
    domain_instructions = _DOMAIN_CRITIC_INSTRUCTIONS.get(kind, "Check for accuracy and completeness.")
    fabrication_block = critic_fabrication_block(FidelityLevel.STRICT, raw_notes_context, _trim, research_context)
    system_prompt = (
        f"Today: {_today()}. "
        f"You are a domain expert critic for a {kind.replace('_', ' ')} deliverable.\n\n"
        f"Domain-specific validation:\n{domain_instructions}\n\n"
        "Also check for: logical gaps, unsupported claims, repetition, and weak transitions.\n\n"
        "For each issue: name the section and give a specific fix instruction. "
        "If the draft passes all checks, say 'Domain review passed.' and stop."
    )
    user_prompt = (
        f"Domain: {kind} | Request: {question}\n\n"
        f"Draft to review:\n{_trim(sections_text, 16000)}"
        f"{fabrication_block}"
    )
    try:
        result = chat_with_self_fix_retry(
            client,
            model=_MODEL_CRITIC,
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            temperature=0.1,
            num_ctx=24576,
            think=True,
            timeout=420,
            retry_attempts=3,
            retry_backoff_sec=1.5,
            validator=_contract_validator(
                stage="specialist_domain_critic",
                min_chars=24,
            ),
        )
        return str(result.text or "").strip()
    except Exception as exc:
        return f"[Domain critic failed: {exc}]"


def _run_section_revision(
    client: OllamaClient,
    section_name: str,
    section_text: str,
    critic_notes: str,
    kind: str,
) -> str:
    system_prompt = (
        f"You are a {kind.replace('_', ' ')} editor. Apply the critic's notes to improve this section. "
        "Preserve the analytical depth and length. Return the complete revised section text only."
    )
    user_prompt = (
        f"Section: {section_name}\n\n"
        f"Current text:\n{section_text}\n\n"
        f"Critic notes:\n{_trim(critic_notes, 1500)}"
    )
    try:
        result = chat_with_self_fix_retry(
            client,
            model=_MODEL_WRITER,
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            temperature=0.2,
            num_ctx=16384,
            think=False,
            timeout=240,
            retry_attempts=3,
            retry_backoff_sec=1.5,
            validator=_contract_validator(
                stage="specialist_section_revision",
                min_chars=120,
            ),
        )
        return str(result.text or "").strip() or section_text
    except Exception:
        return section_text


def _run_compositor(
    client: OllamaClient,
    sections: list[tuple[str, str]],
    section_texts: dict[str, str],
    question: str,
    kind: str,
) -> str:
    assembled_parts: list[str] = []
    for name, _ in sections:
        text = section_texts.get(name, "").strip()
        if text:
            assembled_parts.append(f"### {name}\n\n{text}")
    assembled = "\n\n---\n\n".join(assembled_parts)

    system_prompt = (
        f"Today: {_today()}. "
        f"You are a final compositor for a {kind.replace('_', ' ')} deliverable. "
        "Tasks:\n"
        "1. Write a professional title.\n"
        "2. Write a brief executive introduction (3-4 sentences).\n"
        "3. Smooth transitions between sections.\n"
        "4. Write a conclusion that synthesizes key findings.\n"
        "5. Ensure consistent professional tone throughout.\n\n"
        "Output clean markdown. Use ## for main section headers. No meta-commentary."
    )
    user_prompt = (
        f"Domain: {kind} | Request: {question}\n\n"
        f"Sections to assemble:\n\n{assembled}"
    )
    try:
        result = chat_with_self_fix_retry(
            client,
            model=_MODEL_COMPOSITOR,
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            temperature=0.2,
            num_ctx=24576,
            think=False,
            timeout=480,
            retry_attempts=4,
            retry_backoff_sec=2.0,
            validator=_contract_validator(
                stage="specialist_compositor",
                required_markers=("##",),
                min_chars=320,
            ),
        )
        return str(result.text or "").strip()
    except Exception:
        fallback_lines = [f"# {question[:80]}", ""]
        for name, _ in sections:
            text = section_texts.get(name, "").strip()
            if text:
                fallback_lines.append(f"## {name}\n\n{text}")
        return "\n\n".join(fallback_lines)


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------

def run_specialist_pool(
    question: str,
    repo_root: Path,
    project_slug: str,
    bus: Any,
    topic_type: str = "general",
    target: str = "document",
    research_context: str = "",
    raw_notes_context: str = "",
    sources_context: str = "",
    cancel_checker: Callable[[], bool] | None = None,
    progress_callback: Callable[[str, dict[str, Any]], None] | None = None,
) -> dict[str, Any]:
    """Run the specialist domain pipeline and return assembled text."""

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

    kind = str(target).strip().lower() or "document"
    bus.emit("specialist_pool", "start", {"question": question, "target": kind, "topic_type": topic_type})

    sections = _DOMAIN_SECTIONS.get(kind, _DOMAIN_SECTIONS.get(topic_type, _SECTIONS_HISTORY))
    client = OllamaClient()

    # Step 1: Outline
    if _cancelled():
        return {"ok": False, "message": "Cancelled before outline.", "body": ""}

    _progress("specialist_outline_started", {"sections": [n for n, _ in sections]})
    outline = _run_outline(
        client, question, sections, research_context,
        raw_notes_context, kind,
    )
    _progress("specialist_outline_completed", {"preview": outline[:300]})

    # Parse outline into per-section theses
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

    for name, hint in sections:
        if name not in section_theses or not section_theses[name]:
            section_theses[name] = hint

    # Step 2: Section writing (parallel)
    if _cancelled():
        return {"ok": False, "message": "Cancelled before section writing.", "body": ""}

    max_workers = min(3, len(sections))

    def _write_one(idx_name_hint: tuple[int, str, str]) -> tuple[str, str]:
        i, section_name, _ = idx_name_hint
        if _cancelled():
            return section_name, "[cancelled]"
        thesis = section_theses.get(section_name, "")
        _progress("specialist_section_started", {
            "section": section_name, "index": i + 1, "total": len(sections),
        })
        text = _run_section_writer(
            client, section_name, thesis, outline,
            question, research_context, kind,
            sources_context=sources_context,
            raw_notes_context=raw_notes_context,
        )
        _progress("specialist_section_completed", {
            "section": section_name, "index": i + 1, "total": len(sections),
            "preview": text[:200],
        })
        return section_name, text

    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        pairs = list(executor.map(
            _write_one,
            [(i, name, hint) for i, (name, hint) in enumerate(sections)],
        ))
    section_texts: dict[str, str] = {name: text for name, text in pairs}

    if _cancelled():
        return {"ok": False, "message": "Cancelled during section writing.", "body": ""}

    # Step 3: Domain critic
    all_sections_text = "\n\n".join(
        f"### {n}\n\n{section_texts.get(n, '')}" for n, _ in sections
    )
    _progress("specialist_critic_started", {})
    critic_notes = _run_domain_critic(client, all_sections_text, question, kind, raw_notes_context, research_context)
    _progress("specialist_critic_completed", {"preview": critic_notes[:300]})

    # Step 4: Revision pass
    if critic_notes and "review passed" not in critic_notes.lower() and not _cancelled():
        flagged: list[str] = []
        for name, _ in sections:
            if name.lower() in critic_notes.lower():
                flagged.append(name)
        if flagged:
            _progress("specialist_revision_started", {"sections_flagged": flagged})
            for section_name in flagged:
                if _cancelled():
                    break
                revised = _run_section_revision(
                    client, section_name, section_texts.get(section_name, ""),
                    critic_notes, kind,
                )
                section_texts[section_name] = revised
            _progress("specialist_revision_completed", {"sections_revised": len(flagged)})

    # Step 5: Compositor
    if _cancelled():
        return {"ok": False, "message": "Cancelled before compositor.", "body": ""}

    _progress("specialist_compositor_started", {"total_sections": len(sections)})
    final_body = _run_compositor(client, sections, section_texts, question, kind)
    _progress("specialist_compositor_completed", {"chars": len(final_body)})

    # Step 6: Quality gate
    passed, gate_issues = _quality_gate(final_body, kind)
    if not passed and not _cancelled():
        _progress("specialist_quality_gate_failed", {"issues": gate_issues})
        # One fix pass for quality gate failures
        fix_instructions = "\n".join(f"- {issue}" for issue in gate_issues)
        fix_system = (
            f"You are a {kind.replace('_', ' ')} editor. Fix these specific issues in the document:\n"
            f"{fix_instructions}\n\n"
            "Return the complete corrected document in markdown. Do not truncate."
        )
        try:
            fixed = chat_with_self_fix_retry(
                client,
                model=_MODEL_COMPOSITOR,
                system_prompt=fix_system,
                user_prompt=f"Document to fix:\n{_trim(final_body, 16000)}",
                temperature=0.2,
                num_ctx=24576,
                think=False,
                timeout=300,
                retry_attempts=2,
                retry_backoff_sec=1.5,
                validator=_contract_validator(
                    stage="specialist_quality_fix",
                    min_chars=220,
                ),
            )
            fixed_str = str(fixed.text or "").strip()
            if fixed_str and len(fixed_str) >= len(final_body) * 0.6:
                final_body = fixed_str
        except Exception:
            pass
        _progress("specialist_quality_gate_fix_completed", {"chars": len(final_body)})

    bus.emit("specialist_pool", "completed", {
        "project": project_slug, "target": kind, "chars": len(final_body),
    })

    return {
        "ok": True,
        "body": final_body,
        "outline": outline,
        "critic_notes": critic_notes,
        "quality_gate_passed": passed,
        "quality_gate_issues": gate_issues if not passed else [],
        "sections_written": list(section_texts.keys()),
        "message": f"{kind.replace('_', ' ').title()} complete — {len(final_body):,} chars, {len(sections)} sections.",
    }
