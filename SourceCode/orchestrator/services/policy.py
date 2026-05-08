from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from shared_tools.phase0 import lane_to_pipeline, serious_mode_enabled
from taxonomy.domains import domain_for_topic_type, normalize_domain
from taxonomy.make_types import infer_make_type
from taxonomy.research_focus import infer_research_focus


_LIVE_TOKENS = {
    "today", "tonight", "live", "weigh-in", "weighin", "start time", "what time", "stream", "watch", "odds", "line", "favorite", "underdog",
    "upcoming", "next event", "fight card", "card", "schedule", "scheduled", "bout", "next fight", "next ufc", "next ppv",
    "when is", "event date", "fight night", "main event", "co-main", "prelims", "early prelims",
}
_WORKSPACE_TOKENS = {
    "file", "repo", "repository", "patch", "refactor", "function", "class", "code", "workspace", "bug", "python", "javascript", "typescript"
}
_HOME_TOKENS = {
    "shopping list", "reminder", "routine", "family", "calendar", "task", "todo", "appointment"
}
_DEEP_TOKENS = {
    "compare", "analyze", "analysis", "deep dive", "breakdown", "history", "historical", "timeline", "evidence", "pros and cons", "tradeoffs", "forecast"
}
_SIMPLE_PATTERNS = [
    re.compile(r"^\s*(what|when|where|who)\b", re.I),
    re.compile(r"\bhow many\b", re.I),
]

CODE_MAKE_TYPES = frozenset(
    {
        "web_app",
        "desktop_app",
        "cli_tool",
        "developer_tool",
        "ui_component",
        "tui_app",
        "library_sdk",
        "backend_service",
        "full_application",
        "benchmark_suite",
        "data_pipeline",
        "model_runtime_system",
    }
)


def _resolve_domain(make_type: str, inferred_domain: str) -> str:
    if str(make_type or "").strip().lower() in CODE_MAKE_TYPES:
        return "computer_science_programming"
    return str(inferred_domain or "").strip() or "general_research"


class IntentRouter:
    RESEARCH_TERMS = [
        "research", "analyze", "compare", "study", "investigate", "find sources", "sources", "citations",
    ]
    UI_TERMS = [
        "ui", "ux", "frontend", "front-end", "flask", "javascript", "vanilla js", "web app", "landing page",
    ]
    UI_ACTION_TERMS = [
        "build", "create", "make", "generate", "draft", "design", "redesign", "implement", "code", "develop", "scaffold", "spec", "prototype", "fix",
    ]
    PERSONAL_STRONG_TERMS = [
        "appointment", "calendar", "schedule", "remind me", "set reminder", "my reminders", "shopping list",
        "honey do", "personal assistant", "for me personally",
    ]
    PET_OR_RESEARCH_CONTEXT_TERMS = [
        "dog", "pet", "puppy", "aafco", "allerg", "activity level", "weight", "breed", "feeding", "brand", "retailer",
    ]
    CONVERSATION_TERMS = [
        "what do you think", "do you think", "be honest", "tell me straight", "how are you",
        "how's it going", "hows it going", "you there", "you good", "fair enough",
        "makes sense", "i agree", "i disagree", "that's funny", "that is funny",
        "that's wild", "that is wild", "that's crazy", "that is crazy",
    ]

    @staticmethod
    def _looks_like_followup_answers(text: str) -> bool:
        low = text.lower()
        if "follow-up questions" in low or "follow up questions" in low:
            return True
        numbered = len(re.findall(r"(^|\n)\s*\d+[\).\s]", low))
        has_q = "?" in low
        return numbered >= 2 and has_q

    @staticmethod
    def _contains_term(text: str, term: str) -> bool:
        token = term.strip().lower()
        if not token:
            return False
        low = text.lower()
        if " " in token or "-" in token:
            return token in low
        return bool(re.search(rf"\b{re.escape(token)}\b", low))

    @classmethod
    def _any_term(cls, text: str, terms: list[str]) -> bool:
        return any(cls._contains_term(text, term) for term in terms)

    @classmethod
    def _is_explicit_ui_intent(cls, text: str) -> bool:
        low = text.lower().strip()
        if low.startswith("/ui"):
            return True
        has_ui_domain = cls._any_term(low, cls.UI_TERMS)
        has_ui_action = cls._any_term(low, cls.UI_ACTION_TERMS)
        explicit_phrases = ["ui spec", "build ui", "build a web app", "build web app", "frontend spec", "implementation spec"]
        return (has_ui_domain and has_ui_action) or any(phrase in low for phrase in explicit_phrases)

    def keyword_route(self, user_text: str, project_slug: str = "") -> tuple[str, bool]:
        text = user_text.lower()
        project_key = (project_slug or "").strip().lower()
        is_personal_project = project_key in {"_personal", "personal"}

        if self._any_term(text, self.CONVERSATION_TERMS):
            if serious_mode_enabled():
                return ("research", False)
            return ("conversation", True)
        if self._any_term(text, self.RESEARCH_TERMS):
            return ("research", True)
        if self._is_explicit_ui_intent(text):
            return ("ui", True)
        if is_personal_project:
            if serious_mode_enabled():
                return ("research", False)
            return ("personal", True)
        if self._looks_like_followup_answers(text):
            return ("research", True)
        if self._any_term(text, self.PET_OR_RESEARCH_CONTEXT_TERMS):
            return ("research", True)
        if self._any_term(text, self.PERSONAL_STRONG_TERMS):
            if serious_mode_enabled():
                return ("research", False)
            return ("personal", True)
        # Short ambiguous messages (≤4 words, no domain keywords) → hint conversation
        words = text.split()
        if len(words) <= 4 and not self._any_term(text, self.RESEARCH_TERMS + self.PERSONAL_STRONG_TERMS):
            return ("conversation", False)
        return ("research", False)

    def llm_route(
        self,
        text: str,
        client: Any,
        model_cfg: dict,
        *,
        recent_context: str = "",
        keyword_lane: str = "",
    ) -> str | None:
        model = str(model_cfg.get("model", "")).strip()
        if not model or not client:
            return None
        system_prompt = (
            "You are a request classifier. Reply with ONLY one word — research, personal, ui, or conversation.\n"
            "research: fact-finding, analysis, questions about the world, explain/compare/summarize topics\n"
            "personal: tasks, reminders, calendar, life admin, family, scheduling, personal planning\n"
            "ui: building software, apps, websites, code, front-end design, implementation specs\n"
            "conversation: greetings, thanks, social acknowledgments, casual chat, follow-up reactions, opinions, vibe checks, banter\n\n"
            "Use the recent conversation context to disambiguate follow-up messages. "
            "If the current message is a follow-up to a research or personal thread, continue that lane. "
            "Prefer conversation when the user is simply talking, reacting, asking your take, or making social contact rather than asking for actual research, task execution, or planning."
        )
        context_hint = ""
        if recent_context.strip():
            context_hint = f"\n\n{recent_context.strip()}"
        if keyword_lane:
            context_hint += f"\n\nKeyword classifier suggests: {keyword_lane} (override only if clearly wrong)"
        user_prompt = f'Classify this request:\n"{text[:400]}"{context_hint}'
        try:
            result = client.chat(
                model=model,
                system_prompt=system_prompt,
                user_prompt=user_prompt,
                temperature=0.0,
                num_ctx=1024,
                think=False,
                timeout=8,
                retry_attempts=1,
                retry_backoff_sec=0.5,
            )
            lane = str(result or "").strip().lower().split()[0] if result else ""
            if lane in {"research", "personal", "ui", "conversation"}:
                return lane
        except Exception:
            pass
        return None

    def route(
        self,
        user_text: str,
        project_slug: str = "",
        *,
        client: Any | None = None,
        model_cfg: dict | None = None,
        recent_context: str = "",
    ) -> str:
        lane, confident = self.keyword_route(user_text, project_slug)
        if confident:
            return lane
        if client and model_cfg:
            llm_lane = self.llm_route(
                user_text,
                client,
                model_cfg,
                recent_context=recent_context,
                keyword_lane=lane,
            )
            if llm_lane:
                if serious_mode_enabled() and llm_lane in {"personal", "conversation"}:
                    return "research"
                return llm_lane
        return lane


def estimate_query_complexity(query: str) -> str:
    text = " ".join(str(query or "").split())
    low = text.lower()
    token_count = len(re.findall(r"\w+", low))
    if any(tok in low for tok in _DEEP_TOKENS) or token_count >= 22:
        return "deep"
    if token_count <= 10 and any(p.search(text) for p in _SIMPLE_PATTERNS):
        return "simple"
    return "medium"


def classify_query_mode(query: str, *, context: dict[str, Any] | None = None) -> str:
    low = " ".join(str(query or "").split()).lower()
    if any(tok in low for tok in _WORKSPACE_TOKENS):
        return "workspace_code"
    if any(tok in low for tok in _HOME_TOKENS):
        return "personal_home"
    if any(tok in low for tok in _LIVE_TOKENS):
        return "live_event"
    complexity = estimate_query_complexity(low)
    if complexity == "deep":
        return "deep_research"
    if complexity == "simple":
        return "simple_factual"
    return "general_research"


def should_run_full_foraging(mode: str, complexity: str | None = None) -> bool:
    mode = str(mode or "").strip().lower()
    complexity = str(complexity or "").strip().lower()
    if mode in {"workspace_code", "personal_home"}:
        return False
    if mode in {"simple_factual", "live_event"}:
        return False
    if mode == "deep_research":
        return True
    return complexity != "simple"


def should_run_full_research(mode: str, complexity: str | None = None) -> bool:
    return should_run_full_foraging(mode, complexity)


def recommend_lane_override(mode: str, current_lane: str) -> str | None:
    mode = str(mode or "").strip().lower()
    if mode == "workspace_code":
        return "project"
    if mode == "personal_home":
        return "personal"
    if mode in {"simple_factual", "live_event", "deep_research", "general_research"}:
        return "research"
    return current_lane or None


def recommend_pipeline_override(mode: str, current_pipeline: str) -> str | None:
    lane = recommend_lane_override(mode, current_pipeline)
    if lane is None:
        return None
    return lane_to_pipeline(lane)


@dataclass(slots=True)
class RoutingDecision:
    lane: str
    pipeline: str
    query_mode: str
    complexity: str
    domain: str
    make_type: str
    make_intent: str
    research_focus: str
    lane_override: str | None = None
    should_run_foraging: bool = False
    meta: dict[str, Any] = field(default_factory=dict)

    def as_dict(self) -> dict[str, Any]:
        return {
            "lane": self.lane,
            "pipeline": self.pipeline,
            "query_mode": self.query_mode,
            "complexity": self.complexity,
            "domain": self.domain,
            "make_type": self.make_type,
            "make_intent": self.make_intent,
            "research_focus": self.research_focus,
            "lane_override": self.lane_override,
            "should_run_foraging": self.should_run_foraging,
            "meta": dict(self.meta),
        }


class RoutingPolicy:
    """Single source of truth for request routing and query-mode heuristics."""

    def __init__(self, repo_root: Path, intent_router: IntentRouter | None = None) -> None:
        self.repo_root = repo_root
        self.intent_router = intent_router or IntentRouter()

    def decide(
        self,
        text: str,
        *,
        project_slug: str,
        topic_type: str = "general",
        client: Any | None = None,
        model_cfg: dict[str, Any] | None = None,
        current_lane: str = "research",
        recent_context: str = "",
    ) -> RoutingDecision:
        normalized = (text or "").strip()
        lane = self.intent_router.route(
            normalized,
            project_slug=project_slug,
            client=client,
            model_cfg=model_cfg,
            recent_context=recent_context,
        )
        query_mode = classify_query_mode(normalized, context={"project": project_slug, "topic_type": topic_type})
        complexity = estimate_query_complexity(normalized)
        lane_override = recommend_lane_override(query_mode, lane or current_lane)
        should_forage = should_run_full_foraging(query_mode, complexity)
        pipeline = lane_to_pipeline(lane)
        make_type = infer_make_type(text=normalized, target="", lane=lane)
        domain = _resolve_domain(
            make_type,
            normalize_domain(domain_for_topic_type(topic_type)),
        )
        make_intent = query_mode
        research_focus = infer_research_focus(
            text=normalized,
            query_mode=query_mode,
            pipeline=pipeline,
            make_type=make_type,
        )
        return RoutingDecision(
            lane=lane,
            pipeline=pipeline,
            query_mode=query_mode,
            complexity=complexity,
            domain=domain,
            make_type=make_type,
            make_intent=make_intent,
            research_focus=research_focus,
            lane_override=lane_override,
            should_run_foraging=should_forage,
            meta={
                "project": project_slug,
                "topic_type": topic_type,
                "domain": domain,
                "make_type": make_type,
                "make_intent": make_intent,
                "research_focus": research_focus,
                "chars": len(normalized),
                "words": len([p for p in normalized.split() if p]),
            },
        )


__all__ = [
    "IntentRouter",
    "RoutingDecision",
    "RoutingPolicy",
    "classify_query_mode",
    "estimate_query_complexity",
    "recommend_lane_override",
    "recommend_pipeline_override",
    "should_run_full_research",
    "should_run_full_foraging",
]
