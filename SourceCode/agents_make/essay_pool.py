"""Essay / Report / Brief generation pool.

Pipeline:
    1. Outline       — qwen2.5:7b reads research context + request, produces
                        section-by-section thesis map.
    2. Section write — qwen3:8b writes sections in parallel (max 3 workers,
                        ~400 words each), each receiving its specific thesis
                        + research context so it stays grounded.
    3. Critic        — deepseek-r1:8b reads all
                        sections and flags gaps, repetition, unsupported claims,
                        thesis drift. Skipped for "brief" target.
    4. Revision      — qwen3:8b applies critic notes to flagged sections.
                        Skipped for "brief" target.
    5. Compositor    — qwen2.5:7b assembles final document: title, smooth
                        transitions, consistent voice, final conclusion.
    6. Proofreader   — deepseek-r1:8b reads the assembled essay and checks for
                        factual contradictions, truncated sections, and tense
                        drift. Auto-applies fixes if issues found.
                        Skipped for "brief" target.

Topic-type-aware section templates ensure a history essay is structured
differently from a finance report or a science explainer. Underground topics
route all agents through the unrestricted model.
"""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

from shared_tools.feedback_learning import FeedbackLearningEngine
from shared_tools.fidelity_policy import FidelityLevel, fidelity_for, writer_constraint_block, evidence_key_block, thin_research_warning
from shared_tools.llm_retry import chat_with_self_fix_retry
from shared_tools.model_routing import lane_model_config
from shared_tools.ollama_client import OllamaClient


# ---------------------------------------------------------------------------
# Section templates
# ---------------------------------------------------------------------------

_SECTIONS_HISTORY = [
    ("Introduction & Thesis",       "Establish the historical question, time period, and central argument. Hook the reader with its significance."),
    ("Historical Background",       "Provide context: political, social, or economic conditions that set the stage. Use specific dates and actors."),
    ("Key Events & Turning Points", "Narrate pivotal events in sequence. Cite evidence for causation vs. correlation."),
    ("Key Actors & Motivations",    "Analyze the agents of change: who acted, what they wanted, and why they succeeded or failed."),
    ("Historiographical Debate",    "Present competing scholarly interpretations. What do historians disagree on and why? Name schools of thought."),
    ("Conclusion & Legacy",         "Synthesize the argument. What does this history mean? What precedents did it set for later events?"),
]

_SECTIONS_SCIENCE = [
    ("Introduction & Core Claim",      "State the scientific question and the thesis about the current state of knowledge."),
    ("Scientific Background",          "Cover prerequisite concepts, established consensus, and the field's prior trajectory."),
    ("Evidence & Methodology",         "Analyze key studies, experiments, and data. Note methodology quality and replication status."),
    ("Competing Interpretations",      "Where does the science actively disagree? What are the frontier debates? Flag consensus vs. contested."),
    ("Practical Implications",         "Real-world applications, technology readiness level, and societal impact."),
    ("Conclusion & Open Questions",    "Synthesize findings and identify what remains unknown, contested, or dependent on future research."),
]

_SECTIONS_FINANCE = [
    ("Executive Summary",           "The investment thesis or market position in 3–5 sentences. Bottom line up front."),
    ("Market Context",              "Macro environment, sector dynamics, and the conditions that frame this analysis."),
    ("Core Findings",               "Specific data points, valuations, trend analysis. Cite figures with sources and dates."),
    ("Risk Factors",                "Downside scenarios, tail risks, liquidity constraints, regulatory headwinds. Be direct about what breaks the thesis."),
    ("Thesis & Recommendation",     "Actionable position with confidence level and key assumptions stated explicitly."),
    ("Caveats & Disclosures",       "Uncertainty disclosures, what would change the recommendation, timeline dependencies."),
]

_SECTIONS_MEDICAL = [
    ("Clinical Summary",            "The condition, intervention, or topic in plain language. Who this affects and why it matters."),
    ("Evidence Review",             "Peer-reviewed findings by evidence tier: RCT > observational > case study > expert opinion."),
    ("Risk & Safety Profile",       "Adverse events, contraindications, drug interactions, population-specific risks. Include any black box warnings."),
    ("Clinical Guidelines",         "Current WHO / CDC / NIH / specialty society recommendations and their evidence basis."),
    ("Patient Considerations",      "Practical implications. What questions a patient should bring to a clinician."),
    ("Limitations & Caveats",       "This is not medical advice. Evidence gaps, study limitations, jurisdiction and population differences."),
]

_SECTIONS_ANIMAL_CARE = [
    ("Care Summary",                "The animal-care issue, intervention, or question in plain language. Name the species and why it matters."),
    ("Evidence Review",             "Vet-reviewed and evidence-based findings first. Distinguish clinical guidance from breeder, trainer, or anecdotal advice."),
    ("Risk & Safety Profile",       "Urgent red flags, contraindications, toxicity risks, species-specific sensitivities, and when home care is not appropriate."),
    ("Veterinary Guidance",         "Current guidance from veterinary or animal-welfare authorities, including vaccine, nutrition, behavior, or preventive-care recommendations."),
    ("Owner Considerations",        "Practical decisions for the owner or caregiver: monitoring, environment, follow-up, and questions to bring to a veterinarian."),
    ("Limitations & Caveats",       "This is not veterinary advice. Evidence gaps, breed/species variation, and cases that require direct professional evaluation."),
]

_SECTIONS_POLITICS = [
    ("Introduction & Frame",        "The political question or event and the analytical lens being applied."),
    ("Policy & Governance Context", "What the law, policy, or event actually says — factual, text-grounded, not editorial."),
    ("Stakeholder Analysis",        "Key actors, stated vs. actual interests, funding sources, alliances, and power dynamics."),
    ("Evidence & Arguments",        "The strongest arguments on each side with evidence quality noted explicitly."),
    ("Counter-Arguments",           "The best case against the thesis. What the dominant framing misses or gets wrong."),
    ("Conclusion & Outlook",        "Synthesis and trajectory: where does this go from here, and what signals to watch."),
]

_SECTIONS_SPORTS = [
    ("Introduction & Stakes",       "What event or matchup this analyzes and why it matters."),
    ("Context & Current Form",      "Current standings, recent results, roster state, event context, scheduling notes."),
    ("Statistical Analysis",        "Head-to-head records, key performance metrics, historical trajectory. Cite specific figures."),
    ("Risk & Uncertainty Factors",  "Injuries, undisclosed roster changes, officiating, venue, momentum, and other volatility drivers."),
    ("Analysis & Outlook",          "Synthesis of all factors into a coherent assessment of what is most likely and why."),
    ("Conclusion",                  "Key takeaways and remaining open questions that could change the picture."),
]

_SECTIONS_UNDERGROUND = [
    ("Introduction",                "Frame the topic without filters. What this is and why it matters operationally."),
    ("Background & Operational Context", "How this domain actually works. Key actors, venues, platforms, and real practices."),
    ("Technical & Procedural Analysis",  "How things work mechanically. Methods, tools, infrastructure, step-level details."),
    ("Risk & Threat Landscape",     "What actually gets people caught, burned, or ripped off. Real failure modes with specifics."),
    ("Market & Trust Dynamics",     "Pricing, reputation systems, escrow mechanics, platform active/exit/compromised status."),
    ("Conclusion",                  "Synthesis of operational realities and the most important takeaways."),
]

_SECTIONS_TECHNICAL = [
    ("Introduction & Problem",      "The technical problem or question this addresses and why it matters now."),
    ("Architecture & Design",       "System design tradeoffs, technology choices, competing approaches with evidence."),
    ("Implementation Analysis",     "Concrete implementation details, library/framework comparisons, known gotchas, version specifics."),
    ("Risk & Failure Modes",        "Security vulnerabilities, performance bottlenecks, maintenance burden, technical debt."),
    ("Ecosystem & Alternatives",    "Market maturity, adoption trends, community support, competitive alternatives."),
    ("Conclusion & Recommendations","Synthesis and practical guidance for someone who needs to act on this."),
]

_SECTIONS_MATH = [
    ("Introduction & Problem Statement", "Define the mathematical question, domain, or concept being analyzed."),
    ("Foundational Concepts",       "Required background: definitions, axioms, prior results this builds on."),
    ("Core Analysis",               "The main mathematical work: proofs, derivations, computational approaches."),
    ("Applications & Examples",     "Concrete examples, use cases, numerical demonstrations."),
    ("Limitations & Open Problems", "Where the approach breaks down, unsolved problems, active research frontiers."),
    ("Conclusion",                  "Synthesis and significance of the analysis."),
]

_SECTIONS_GENERAL = [
    ("Introduction & Thesis",       "Frame the topic and state the central argument clearly."),
    ("Background & Context",        "Essential context: key actors, origins, why this topic exists."),
    ("Core Analysis",               "The main analytical work: evidence, competing views, logical structure."),
    ("Implications & Second-Order Effects", "What this means downstream. Who is affected and how."),
    ("Uncertainties & Open Questions", "What remains unknown, contested, or dependent on assumptions."),
    ("Conclusion",                  "Synthesis and the most important takeaway for someone who needs to act on this."),
]

_SECTIONS_PARENTING = [
    ("Overview & Context",              "What this developmental topic is, the age/stage it applies to, and why it matters for this child's specific situation."),
    ("What the Research Says",          "Evidence-based findings, with study quality noted (evidence tier + publication year). Flag where research samples are limited (e.g., predominantly male ASD studies, clinical vs. community populations)."),
    ("Neurodiversity-Affirming Lens",   "Strengths-based and identity-affirming perspectives. Include autistic self-advocate viewpoints where available. Note where mainstream clinical framing diverges from affirming frameworks and what that means practically."),
    ("Practical Strategies",            "Concrete, actionable approaches for home, school, and therapy settings. Distinguish well-supported approaches from anecdotal ones. Include low-cost and high-access options."),
    ("Working With Professionals",      "What to ask pediatricians, therapists, and school teams specifically. What to advocate for. Questions to bring to the next appointment."),
    ("Limitations & Open Questions",    "Research gaps, areas of active debate, and where lived experience and community knowledge outpaces the clinical literature."),
]

_SECTIONS_BRIEF = [
    ("Executive Summary",   "Bottom line: the most important finding or position in 2–3 sentences."),
    ("Key Findings",        "The 3–5 most significant findings from research, each with a confidence note."),
    ("Risks & Next Actions", "Primary risks or uncertainties and the most important recommended next steps."),
]

_SECTIONS_BLOG = [
    ("Hook & Headline",   "Open with an attention-grabbing headline and a 1-2 sentence hook."),
    ("Context & Why Now", "Brief background: why this topic matters right now. Conversational, not academic."),
    ("Core Content",      "Main value: key insights, how-tos, or analysis. Subheadings, short paragraphs, concrete examples."),
    ("Takeaway & CTA",   "Clear takeaway and call to action: what should the reader do, think, or explore next?"),
]

_SECTIONS_SOCIAL_POST = [
    ("Hook",           "One punchy sentence (under 40 words) that stops the scroll."),
    ("Body",           "2-3 concise sentences expanding the hook. Under 200 words total. Plain language."),
    ("Call to Action", "One sentence: what should the reader do next?"),
]

_SECTION_MAP: dict[str, list[tuple[str, str]]] = {
    "history":        _SECTIONS_HISTORY,
    "science":        _SECTIONS_SCIENCE,
    "finance":        _SECTIONS_FINANCE,
    "medical":        _SECTIONS_MEDICAL,
    "animal_care":    _SECTIONS_ANIMAL_CARE,
    "politics":       _SECTIONS_POLITICS,
    "sports":         _SECTIONS_SPORTS,
    "underground":    _SECTIONS_UNDERGROUND,
    "technical":      _SECTIONS_TECHNICAL,
    "math":           _SECTIONS_MATH,
    "parenting":      _SECTIONS_PARENTING,
    "general":        _SECTIONS_GENERAL,
    "current_events": _SECTIONS_GENERAL,
    "blog":           _SECTIONS_BLOG,
    "social_post":    _SECTIONS_SOCIAL_POST,
}


def _sections_for(topic_type: str, target: str) -> list[tuple[str, str]]:
    _TARGET_SECTIONS = {"brief": _SECTIONS_BRIEF, "blog": _SECTIONS_BLOG, "social_post": _SECTIONS_SOCIAL_POST}
    if target in _TARGET_SECTIONS:
        return _TARGET_SECTIONS[target]
    return _SECTION_MAP.get(str(topic_type).strip().lower(), _SECTIONS_GENERAL)


# ---------------------------------------------------------------------------
# Model routing helpers
# ---------------------------------------------------------------------------

_MODEL_OUTLINE    = "qwen3:8b"
_MODEL_WRITER     = "qwen3:8b"
_MODEL_CRITIC     = "deepseek-r1:8b"
_MODEL_COMPOSITOR = "qwen3:8b"

# Underground: abliterated-only throughout — no filtered models anywhere
_MODEL_UNRESTRICTED = "qwen3:8b"


def _models_for(topic_type: str) -> tuple[str, str, str, str]:
    """Returns (outline, writer, critic, compositor) model names."""
    if str(topic_type).strip().lower() == "underground":
        return _MODEL_UNRESTRICTED, _MODEL_UNRESTRICTED, _MODEL_UNRESTRICTED, _MODEL_UNRESTRICTED
    return _MODEL_OUTLINE, _MODEL_WRITER, _MODEL_CRITIC, _MODEL_COMPOSITOR


# ---------------------------------------------------------------------------
# Shared helper
# ---------------------------------------------------------------------------

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


def _outline_validator(section_names: list[str]) -> Callable[[str], str | None]:
    expected = [str(name).strip().lower() for name in section_names if str(name).strip()]

    def _validate(text: str) -> str | None:
        body = str(text or "").strip()
        if not body:
            return "Outline output was empty."
        if "###" not in body:
            return "Outline must use '### [Section Name]' headings."
        low = body.lower()
        matches = sum(1 for name in expected if name and name in low)
        minimum = max(2, min(len(expected), (len(expected) + 1) // 2))
        if matches < minimum:
            return f"Outline did not cover enough required sections ({matches}/{len(expected)})."
        return None

    return _validate


def _notes_validator(approved_phrase: str) -> Callable[[str], str | None]:
    approved_low = str(approved_phrase or "").strip().lower()

    def _validate(text: str) -> str | None:
        body = str(text or "").strip()
        if not body:
            return "Review output was empty."
        low = body.lower()
        if approved_low and approved_low in low:
            return None
        if "###" in body and ":" in body:
            return None
        return "Review output must either explicitly approve or return section-scoped notes."

    return _validate


# ---------------------------------------------------------------------------
# Pipeline steps
# ---------------------------------------------------------------------------

def _run_outline(
    client: OllamaClient,
    model: str,
    question: str,
    sections: list[tuple[str, str]],
    research_context: str,
    topic_type: str,
    target: str,
    sources_context: str = "",
    level: FidelityLevel = FidelityLevel.STRICT,
) -> str:
    section_list = "\n".join(f"  {i+1}. {name}: {hint}" for i, (name, hint) in enumerate(sections))
    thin_warn = thin_research_warning(level, len(research_context))
    system_prompt = (
        f"Today: {_today()}. "
        "You are an essay strategist. Given research context and a writing request, "
        "produce a tight outline: one thesis sentence per section that the writer will follow. "
        "Use facts and names from the research only — not from your training knowledge, which may be wrong. "
        "Where a web source directly supports a section, note the URL so the writer can cite it. "
        f"Output each section as: '### [Section Name]\\n[1-2 sentence thesis]'. Nothing else."
        f"{thin_warn}"
    )
    sources_block = f"\n\nWeb sources (URLs available for citation):\n{_trim(sources_context, 4000)}" if sources_context.strip() else ""
    user_prompt = (
        f"Writing target: {target} | Topic type: {topic_type}\n"
        f"Request: {question}\n\n"
        f"Sections to plan:\n{section_list}\n\n"
        f"Research context (ground every section thesis in real findings):\n"
        f"{_trim(research_context, 12000)}"
        f"{sources_block}"
    )
    try:
        result = _chat_retry(
            client,
            model=model,
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            temperature=0.2,
            num_ctx=20480,
            think=False,
            timeout=300,
            retry_attempts=4,
            retry_backoff_sec=1.5,
            validator=_outline_validator([name for name, _ in sections]),
            self_fix_attempts=3,
        )
        return str(result or "").strip()
    except Exception as exc:
        return "\n".join(f"### {name}\n{hint}" for name, hint in sections)


def _run_section_writer(
    client: OllamaClient,
    model: str,
    section_name: str,
    section_thesis: str,
    outline: str,
    question: str,
    research_context: str,
    topic_type: str,
    target: str,
    word_target: int = 420,
    sources_context: str = "",
    raw_notes_context: str = "",
    level: FidelityLevel = FidelityLevel.STRICT,
) -> str:
    sources_instruction = (
        " When citing a specific fact, include the source URL inline like: (source: URL). "
        "Prefer T1/T2 sources for any claim you mark as evidence-backed."
        if sources_context.strip() else ""
    )
    system_prompt = (
        f"Today: {_today()}. "
        f"You are a section writer for a {target}. "
        "Write ONE section only — do not write other sections. "
        f"Target length: approximately {word_target} words. "
        f"Write in flowing prose. {writer_constraint_block(level)} "
        "Do not use bullet points unless the section clearly calls for a list. "
        "Do not start with the section title — the compositor will handle headers."
        f"{sources_instruction}"
    )
    ev_key = evidence_key_block(level, bool(raw_notes_context.strip()))
    sources_block = f"\n\nWeb sources (cite URLs inline where relevant):\n{_trim(sources_context, 5000)}" if sources_context.strip() else ""
    user_prompt = (
        f"Full outline (for context — write ONLY your assigned section):\n{_trim(outline, 2000)}\n\n"
        f"YOUR SECTION: {section_name}\n"
        f"Thesis to develop: {section_thesis}\n\n"
        f"Research context:{ev_key}\n{_trim(research_context, 10000)}\n\n"
        f"Writing request: {question}"
        f"{sources_block}"
    )
    try:
        result = _chat_retry(
            client,
            model=model,
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            temperature=0.5,
            num_ctx=20480,
            think=False,
            timeout=300,
            retry_attempts=4,
            retry_backoff_sec=1.5,
        )
        return str(result or "").strip()
    except Exception as exc:
        return f"[Section generation failed: {exc}]"


def _run_critic(
    client: OllamaClient,
    model: str,
    sections_text: str,
    question: str,
    topic_type: str,
    raw_notes_context: str = "",
    research_context: str = "",
    level: FidelityLevel = FidelityLevel.STRICT,
) -> str:
    from shared_tools.fidelity_policy import critic_fabrication_block
    fact_block = critic_fabrication_block(level, raw_notes_context, _trim, research_context)
    system_prompt = (
        f"Today: {_today()}. "
        "You are an editorial critic reviewing a draft essay. "
        "Identify specific problems only: logical gaps, unsupported claims, repetition between sections, "
        "thesis drift, and weak transitions. "
        "For each problem, state the section name and a one-sentence fix instruction. "
        "If a section is solid, do not mention it. "
        "Output format: '### [Section Name]\\n- [Problem]: [Fix instruction]'. "
        "If the draft is strong overall, say 'No major issues found.' and stop."
    )
    user_prompt = (
        f"Topic type: {topic_type} | Request: {question}\n\n"
        f"Draft to review:\n{_trim(sections_text, 16000)}"
        f"{fact_block}"
    )
    try:
        result = _chat_retry(
            client,
            model=model,
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            temperature=0.1,
            num_ctx=24576,
            think=False,
            timeout=360,
            retry_attempts=3,
            retry_backoff_sec=1.5,
            validator=_notes_validator("No major issues found."),
            self_fix_attempts=3,
        )
        return str(result or "").strip()
    except Exception as exc:
        return f"[Critic pass failed: {exc}]"


def _run_section_revision(
    client: OllamaClient,
    model: str,
    section_name: str,
    section_text: str,
    critic_notes: str,
    question: str,
) -> str:
    system_prompt = (
        "You are a prose editor. Apply the critic's notes to improve this section. "
        "Preserve the voice and length. Do not add new sections. "
        "Return the complete revised section text only."
    )
    user_prompt = (
        f"Section: {section_name}\n\n"
        f"Current text:\n{section_text}\n\n"
        f"Critic notes for this section:\n{_trim(critic_notes, 1500)}\n\n"
        f"Original request context: {question}"
    )
    try:
        result = _chat_retry(
            client,
            model=model,
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            temperature=0.3,
            num_ctx=16384,
            think=False,
            timeout=240,
            retry_attempts=3,
            retry_backoff_sec=1.5,
        )
        return str(result or "").strip() or section_text
    except Exception:
        return section_text


def _run_compositor(
    client: OllamaClient,
    model: str,
    sections: list[tuple[str, str]],
    section_texts: dict[str, str],
    question: str,
    topic_type: str,
    target: str,
) -> str:
    assembled_parts: list[str] = []
    for name, _ in sections:
        text = section_texts.get(name, "").strip()
        if text:
            assembled_parts.append(f"### {name}\n\n{text}")
    assembled = "\n\n---\n\n".join(assembled_parts)

    system_prompt = (
        f"Today: {_today()}. "
        "You are a final compositor. You receive labelled sections and produce a polished, unified document. "
        "Tasks: (1) Write a strong title. (2) Write a brief introduction paragraph (3–4 sentences) that sets up "
        "the thesis and previews the structure. (3) Smooth transitions between sections — remove any abrupt jumps. "
        "(4) Write a conclusion paragraph (4–6 sentences) that synthesizes the argument and ends with a memorable close. "
        "(5) Ensure consistent voice and tense throughout. "
        "Output clean markdown. Use ## for main section headers. No meta-commentary."
    )
    user_prompt = (
        f"Target format: {target} | Topic: {topic_type}\n"
        f"Original request: {question}\n\n"
        f"Sections to assemble:\n\n{assembled}"
    )
    try:
        result = _chat_retry(
            client,
            model=model,
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            temperature=0.3,
            num_ctx=24576,
            think=False,
            timeout=480,
            retry_attempts=4,
            retry_backoff_sec=2.0,
        )
        return str(result or "").strip()
    except Exception as exc:
        # Fall back to raw assembly if compositor fails
        fallback_lines = [f"# {question[:80]}", ""]
        for name, _ in sections:
            text = section_texts.get(name, "").strip()
            if text:
                fallback_lines.append(f"## {name}\n\n{text}")
        return "\n\n".join(fallback_lines)


def _run_proofreader(
    client: OllamaClient,
    model: str,
    assembled_essay: str,
    question: str,
    topic_type: str,
) -> str:
    """Read the fully assembled essay and flag remaining issues. Returns notes or ''."""
    system_prompt = (
        f"Today: {_today()}. "
        "You are a final proofreader reviewing a complete assembled essay. Check for:\n"
        "1. Factual contradictions between sections (claim X in section A contradicts claim Y in section B).\n"
        "2. Claims stated as established fact that read as speculation — should be hedged.\n"
        "3. Abrupt or truncated endings (section or conclusion cuts off mid-thought).\n"
        "4. Tense or voice inconsistency that disrupts readability.\n"
        "5. Citation URLs that are clearly placeholder (example.com, [URL], etc.).\n"
        "For each issue: name the section and give a one-sentence fix instruction. "
        "If the essay is clean and complete, say 'Proofreading passed.' and stop."
    )
    user_prompt = (
        f"Topic: {topic_type} | Request: {question}\n\n"
        f"Assembled essay:\n{_trim(assembled_essay, 18000)}"
    )
    try:
        result = _chat_retry(
            client,
            model=model,
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            temperature=0.1,
            num_ctx=24576,
            think=False,
            timeout=300,
            retry_attempts=3,
            retry_backoff_sec=1.5,
            validator=_notes_validator("Proofreading passed."),
            self_fix_attempts=3,
        )
        return str(result or "").strip()
    except Exception as exc:
        return f"[Proofreader failed: {exc}]"


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------

def run_essay_pool(
    question: str,
    repo_root: Path,
    project_slug: str,
    bus: Any,
    topic_type: str = "general",
    target: str = "essay",
    research_context: str = "",
    raw_notes_context: str = "",
    sources_context: str = "",
    cancel_checker: Callable[[], bool] | None = None,
    progress_callback: Callable[[str, dict[str, Any]], None] | None = None,
) -> dict[str, Any]:
    """Run the full essay/report/brief pipeline and return the assembled text."""

    def _progress(stage: str, detail: dict[str, Any] | None = None) -> None:
        if not callable(progress_callback):
            return
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

    bus.emit("essay_pool", "start", {"question": question, "target": target, "topic_type": topic_type})

    topic_key = str(topic_type).strip().lower()
    target_key = str(target).strip().lower()
    _level = fidelity_for(target_key, topic_key)
    sections = _sections_for(topic_key, target_key)
    outline_model, writer_model, critic_model, compositor_model = _models_for(topic_key)
    client = OllamaClient()
    run_critic_pass = target_key not in {"brief", "social_post"}

    orchestrator_cfg = lane_model_config(repo_root, "orchestrator_reasoning")
    learning = FeedbackLearningEngine(repo_root, client=client, model_cfg=orchestrator_cfg)
    learned_guidance = learning.guidance_for_lane("make_doc", limit=5)
    if learned_guidance:
        research_context = (learned_guidance + "\n\n" + research_context).strip()

    # ------------------------------------------------------------------
    # Step 1: Outline
    # ------------------------------------------------------------------
    if _cancelled():
        return {"ok": False, "message": "Cancelled before outline.", "body": ""}

    _progress("essay_outline_started", {"sections": [n for n, _ in sections]})
    outline = _run_outline(
        client, outline_model, question, sections,
        research_context, topic_key, target_key,
        sources_context=sources_context,
        level=_level,
    )
    _progress("essay_outline_completed", {"preview": outline[:300]})

    # Parse outline into per-section theses
    # The outline agent writes "### Section Name\nthesis text"
    # Fall back to the template hints if parsing yields nothing useful
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

    # Fill in template hints for any section the outline missed
    for name, hint in sections:
        if name not in section_theses or not section_theses[name]:
            section_theses[name] = hint

    # ------------------------------------------------------------------
    # Step 2: Section writing (parallel — sections are independent)
    # ------------------------------------------------------------------
    _WORD_TARGETS = {"brief": 220, "blog": 300, "social_post": 80}
    word_target = _WORD_TARGETS.get(target_key, 420)
    max_section_workers = min(3, len(sections))

    def _write_one(idx_name_hint: tuple[int, str, str]) -> tuple[str, str]:
        i, section_name, _ = idx_name_hint
        if _cancelled():
            return section_name, "[cancelled]"
        thesis = section_theses.get(section_name, "")
        _progress("essay_section_started", {
            "section": section_name,
            "index": i + 1,
            "total": len(sections),
        })
        text = _run_section_writer(
            client, writer_model, section_name, thesis,
            outline, question, research_context, topic_key, target_key,
            word_target=word_target,
            sources_context=sources_context,
            raw_notes_context=raw_notes_context,
            level=_level,
        )
        _progress("essay_section_completed", {
            "section": section_name,
            "index": i + 1,
            "total": len(sections),
            "preview": text[:200],
        })
        return section_name, text

    with ThreadPoolExecutor(max_workers=max_section_workers) as executor:
        pairs = list(executor.map(
            _write_one,
            [(i, name, hint) for i, (name, hint) in enumerate(sections)],
        ))
    # Preserve section order from the template definition
    section_texts: dict[str, str] = {name: text for name, text in pairs}

    if _cancelled():
        return {"ok": False, "message": "Cancelled during section writing.", "body": ""}

    # ------------------------------------------------------------------
    # Step 3: Editorial critic
    # ------------------------------------------------------------------
    critic_notes = ""
    if run_critic_pass:
        all_sections_text = "\n\n".join(
            f"### {n}\n\n{section_texts.get(n, '')}" for n, _ in sections
        )
        _progress("essay_critic_started", {})
        critic_notes = _run_critic(
            client, critic_model, all_sections_text, question, topic_key,
            raw_notes_context=raw_notes_context,
            research_context=research_context,
            level=_level,
        )
        _progress("essay_critic_completed", {"preview": critic_notes[:300]})

        # ------------------------------------------------------------------
        # Step 4: Revision pass — only sections the critic flagged
        # ------------------------------------------------------------------
        if critic_notes and "no major issues" not in critic_notes.lower() and not _cancelled():
            flagged_sections: list[str] = []
            for name, _ in sections:
                if name.lower() in critic_notes.lower():
                    flagged_sections.append(name)

            if flagged_sections:
                _progress("essay_revision_started", {"sections_flagged": flagged_sections})
                for section_name in flagged_sections:
                    if _cancelled():
                        break
                    # Extract only the critic notes for this specific section
                    relevant_notes = []
                    in_section = False
                    for line in critic_notes.splitlines():
                        if section_name.lower() in line.lower() and line.strip().startswith("#"):
                            in_section = True
                        elif in_section and line.strip().startswith("###"):
                            break
                        elif in_section:
                            relevant_notes.append(line)
                    notes_for_section = "\n".join(relevant_notes).strip() or critic_notes[:600]

                    revised = _run_section_revision(
                        client, writer_model,
                        section_name, section_texts.get(section_name, ""),
                        notes_for_section, question,
                    )
                    section_texts[section_name] = revised
                _progress("essay_revision_completed", {"sections_revised": len(flagged_sections)})

    # ------------------------------------------------------------------
    # Step 5: Compositor
    # ------------------------------------------------------------------
    if _cancelled():
        return {"ok": False, "message": "Cancelled before compositor.", "body": ""}

    _progress("essay_compositor_started", {"total_sections": len(sections)})
    final_body = _run_compositor(
        client, compositor_model,
        sections, section_texts, question, topic_key, target_key,
    )
    _progress("essay_compositor_completed", {"chars": len(final_body)})

    # ------------------------------------------------------------------
    # Step 6: Proofreader pass on assembled essay (skipped for brief)
    # ------------------------------------------------------------------
    proofreader_notes = ""
    if run_critic_pass and not _cancelled():
        _progress("essay_proofreader_started", {})
        proofreader_notes = _run_proofreader(
            client, critic_model, final_body, question, topic_key,
        )
        _progress("essay_proofreader_completed", {"preview": proofreader_notes[:200]})

        if (
            proofreader_notes
            and "proofreading passed" not in proofreader_notes.lower()
            and not _cancelled()
        ):
            _progress("essay_proofreader_fix_started", {})
            fix_system = (
                "You are a prose editor. Apply the proofreader's notes to the complete essay. "
                "Fix ONLY the specific issues listed. Preserve the overall structure, arguments, "
                "and length. Return the complete corrected essay in markdown. Do not truncate."
            )
            fix_user = (
                f"Proofreader notes:\n{_trim(proofreader_notes, 2000)}\n\n"
                f"Original request: {question}\n\n"
                f"Essay to fix:\n{_trim(final_body, 16000)}"
            )
            try:
                fixed = _chat_retry(
                    client,
                    model=compositor_model,
                    system_prompt=fix_system,
                    user_prompt=fix_user,
                    temperature=0.2,
                    num_ctx=24576,
                    think=False,
                    timeout=480,
                    retry_attempts=3,
                    retry_backoff_sec=1.5,
                    validator=lambda candidate: (
                        "Corrected essay looks incomplete."
                        if (len(str(candidate or "").strip()) < max(800, int(len(final_body) * 0.6))
                            or str(candidate or "").strip().endswith(("...", "…")))
                        else None
                    ),
                    self_fix_attempts=2,
                )
                fixed_str = str(fixed or "").strip()
                # Only replace if the fix looks complete (≥ 60% of original length)
                if fixed_str and len(fixed_str) >= len(final_body) * 0.6:
                    final_body = fixed_str
            except Exception:
                pass
            _progress("essay_proofreader_fix_completed", {"chars": len(final_body)})

    bus.emit("essay_pool", "completed", {
        "project": project_slug,
        "target": target_key,
        "topic_type": topic_key,
        "chars": len(final_body),
    })

    return {
        "ok": True,
        "body": final_body,
        "outline": outline,
        "critic_notes": critic_notes,
        "proofreader_notes": proofreader_notes,
        "sections_written": list(section_texts.keys()),
        "message": f"{target.title()} complete — {len(final_body):,} chars, {len(sections)} sections.",
    }
