"""Chat Routing Gate — context check for web-crawl routing decisions."""

from __future__ import annotations

import hashlib
import json
import logging
import re
import time
from pathlib import Path
from threading import Lock
from typing import Any

from shared_tools.activity_bus import ActivityBus, telemetry_emit

LOGGER = logging.getLogger(__name__)

_CONFIDENCE_FLOOR = 0.65
_SEMANTIC_THRESHOLD = 0.72
_SEED_MAX_PER_ROUTE = 64

# Patterns that unambiguously need live web data — skip model checks.
_FORCE_WEB_PATTERNS: tuple[str, ...] = (
    r"\bbreaking news\b",
    r"\blive (?:score|result|update|feed|stream)\b",
    r"\blatest news\b",
    r"\bwhat(?:'s| is) (?:today's|tonight's|this week's)\b",
    r"\bright now\b",
    r"\bas of today\b",
    r"\bsearch the web\b",
    r"\blook it up\b",
    r"\bbrowse the web\b",
    r"\bcurrently\b",
    r"\bnowadays\b",
    r"\bthese days\b",
    r"\bas of (?:202[4-9]|20[3-9]\d)\b",
    r"\b(?:in|since|by)\s+(?:january|february|march|april|may|june|july|august|september|october|november|december)\s+(?:202[4-9]|20[3-9]\d)\b",
    r"\b(?:this|last|next)\s+(?:week|month|quarter|year)\b",
    r"\b(?:202[5-9]|20[3-9]\d)(?:\s|\?|$|\.|,)",
)

# Patterns that are clearly not web-dependent.
_FORCE_NO_WEB_PATTERNS: tuple[str, ...] = (
    r"^(?:ok|okay|thanks|thank you|cool|got it|sounds good|makes sense|fair enough|lol|haha|ha|yep|nope|sure|agreed)\s*[.!?]?\s*$",
    r"^(?:what(?:'s| is)\s+)?[\d\s\+\-\*\/\(\)\.\%\^]+(?:\s*[\+\-\*\/\^]\s*[\d\s\(\)\.]+)+\s*[=\?]?\s*$",
    r"\bsource (?:code|file|tree|of (?:the|this) (?:bug|error|issue|problem|crash|exception))\b",
    r"\bcurrent (?:code|implementation|approach|branch|build|config|setup|state of the (?:code|app|system))\b",
    r"\bweb (?:app|application|server|framework|socket|hook|component|route|endpoint|scraper)\b",
    r"\bweb of (?:connections?|dependencies|lies|calls?|requests?|services?)\b",
    r"\bupdate (?:the|this|my) (?:code|file|document|config|function|variable|class|method|schema|db|database)\b",
)

_SEMANTIC_SEED_NO_WEB: tuple[str, ...] = (
    "thanks",
    "okay got it",
    "what is 2+2",
    "source code of this issue",
    "current implementation in this repo",
    "update this config file",
    "help me debug the web app route",
    "explain this error in my code",
    "rewrite this paragraph",
    "brainstorm ideas with me",
)

_SEMANTIC_GATES: dict[str, Any] = {}
_SEMANTIC_LOCK = Lock()


def _fast_path(text: str) -> dict[str, Any] | None:
    """Return a routing decision immediately for obvious cases."""
    low = text.strip().lower()

    for pat in _FORCE_NO_WEB_PATTERNS:
        if re.search(pat, low, re.IGNORECASE):
            return {"route": "no_web", "confidence": 0.97, "reason": "Matches known non-web pattern.", "skipped": True}

    for pat in _FORCE_WEB_PATTERNS:
        if re.search(pat, low, re.IGNORECASE):
            return {"route": "web", "confidence": 0.97, "reason": "Explicit live-data marker.", "skipped": True}

    return None


def first_force_web_match(text: str) -> str:
    """Return the first explicit web-trigger phrase matched in `text`, if any."""
    low = str(text or "").strip().lower()
    if not low:
        return ""
    for pat in _FORCE_WEB_PATTERNS:
        match = re.search(pat, low, re.IGNORECASE)
        if match:
            return str(match.group(0) or "").strip()
    return ""


def _default_repo_root() -> Path:
    return Path(__file__).resolve().parents[3]


def _hash_text(text: str) -> str:
    norm = " ".join(str(text or "").strip().lower().split())
    return hashlib.sha256(norm.encode("utf-8")).hexdigest()[:16]


def _pattern_to_seed(pattern: str) -> str:
    text = str(pattern or "")
    text = text.replace("\\b", " ")
    text = text.replace("\\s+", " ")
    text = text.replace("(?:", "(")
    text = re.sub(r"[\^\$\?\+\*\[\]\{\}\\]", " ", text)
    text = text.replace("|", " ")
    text = text.replace("(", " ").replace(")", " ")
    text = re.sub(r"\s+", " ", text).strip(" .,:;")
    return text


def _semantic_routes() -> dict[str, list[str]]:
    from orchestrator.text_processing.text_analysis import (
        _EVOLVING_TOPIC_PATTERNS,
        _FACTUAL_LOOKUP_PATTERNS,
        _WEB_OFFER_MARKER_PATTERNS,
    )

    web_seed: list[str] = []
    for raw in list(_WEB_OFFER_MARKER_PATTERNS) + list(_FACTUAL_LOOKUP_PATTERNS):
        seed = _pattern_to_seed(raw)
        if seed:
            web_seed.append(seed)
    for pat in _EVOLVING_TOPIC_PATTERNS:
        seed = _pattern_to_seed(getattr(pat, "pattern", ""))
        if seed:
            web_seed.append(seed)

    no_web_seed: list[str] = []
    for raw in _FORCE_NO_WEB_PATTERNS:
        seed = _pattern_to_seed(raw)
        if seed:
            no_web_seed.append(seed)
    no_web_seed.extend(_SEMANTIC_SEED_NO_WEB)

    def _dedup(rows: list[str]) -> list[str]:
        out: list[str] = []
        seen: set[str] = set()
        for item in rows:
            clean = " ".join(str(item).strip().split()).lower()
            if not clean or clean in seen:
                continue
            seen.add(clean)
            out.append(clean)
        return out[:_SEED_MAX_PER_ROUTE]

    return {
        "web": _dedup(web_seed),
        "no_web": _dedup(no_web_seed),
    }


def _resolve_repo_root(repo_root: Path | None) -> Path:
    return repo_root if isinstance(repo_root, Path) else _default_repo_root()


def _emit_gate_decision(
    repo_root: Path,
    *,
    text: str,
    route: str,
    confidence: float,
    skipped: bool,
    fast_path_hit: bool,
    latency_ms: float,
    reason: str,
) -> None:
    payload = {
        "gate": "chat_routing_gate",
        "input_hash": _hash_text(text),
        "fast_path_hit": bool(fast_path_hit),
        "route": str(route),
        "confidence": round(float(confidence), 4),
        "skipped": bool(skipped),
        "latency_ms": round(float(latency_ms), 2),
        "reason": str(reason or "")[:200],
    }
    telemetry_emit(
        repo_root,
        "gate_decisions.jsonl",
        payload,
        retention_days=14,
    )
    try:
        ActivityBus(repo_root).emit("chat_routing_gate", "route_decision", payload)
    except Exception:
        pass


def _semantic_gate(repo_root: Path):
    root_key = str(repo_root.resolve())
    with _SEMANTIC_LOCK:
        gate = _SEMANTIC_GATES.get(root_key)
        if gate is not None:
            return gate
    from orchestrator.services.semantic_gate import SemanticGate
    gate = SemanticGate(
        repo_root,
        routes=_semantic_routes(),
        threshold=_SEMANTIC_THRESHOLD,
    )
    with _SEMANTIC_LOCK:
        _SEMANTIC_GATES[root_key] = gate
    return gate


def check_web_routing(
    text: str,
    prior_messages: list[dict[str, str]],
    *,
    trigger_reason: str = "keyword",
    repo_root: Path | None = None,
) -> dict[str, Any]:
    """Decide whether the routing system's web-crawl trigger is warranted."""
    started = time.perf_counter()
    resolved_root = _resolve_repo_root(repo_root)

    fast = _fast_path(text)
    if fast is not None:
        _emit_gate_decision(
            resolved_root,
            text=text,
            route=str(fast.get("route", "web")),
            confidence=float(fast.get("confidence", 0.5)),
            skipped=bool(fast.get("skipped", True)),
            fast_path_hit=True,
            latency_ms=(time.perf_counter() - started) * 1000.0,
            reason=str(fast.get("reason", "")),
        )
        return fast

    try:
        semantic = _semantic_gate(resolved_root).classify(text)
        if isinstance(semantic, dict) and not bool(semantic.get("below_threshold", True)):
            route = str(semantic.get("route", "web")).strip().lower()
            if route in {"web", "no_web"}:
                result = {
                    "route": route,
                    "confidence": float(semantic.get("confidence", 0.0)),
                    "reason": "Semantic route match.",
                    "skipped": True,
                }
                _emit_gate_decision(
                    resolved_root,
                    text=text,
                    route=route,
                    confidence=float(result["confidence"]),
                    skipped=True,
                    fast_path_hit=False,
                    latency_ms=(time.perf_counter() - started) * 1000.0,
                    reason=result["reason"],
                )
                return result
    except Exception as exc:
        LOGGER.debug("ChatRoutingGate semantic route failed: %s", exc)

    try:
        from shared_tools.model_routing import lane_model_config
        from shared_tools.ollama_client import OllamaClient

        cfg = lane_model_config(resolved_root, "chat_routing_gate")
        model = str(cfg.get("model", "qwen3:4b")).strip() or "qwen3:4b"
        temperature = float(cfg.get("temperature", 0.0))
        num_ctx = int(cfg.get("num_ctx", 4096))
        timeout = int(cfg.get("timeout_sec", 12))
        fallback_models = cfg.get("fallback_models", ["qwen3:4b"])
        if not isinstance(fallback_models, list):
            fallback_models = ["qwen3:4b"]

        history_lines: list[str] = []
        for row in prior_messages[-6:]:
            role = str(row.get("role", "")).strip().lower()
            content = str(row.get("content", "")).strip()
            if role in ("user", "assistant") and content:
                history_lines.append(f"{role.upper()}: {content[:400]}")
        history_block = "\n".join(history_lines) or "(none)"

        system_prompt = (
            "You are a routing gate for a conversational AI assistant. "
            "A pattern matched in the user's message triggered a possible web data fetch. "
            "Your job: read the full conversation and decide if a web lookup would genuinely help "
            "the assistant give a more accurate or better-grounded answer — or if the trigger was a false positive.\n\n"
            "Route to NO_WEB when:\n"
            "- Pure arithmetic, algebra, or logic puzzles (no lookup needed)\n"
            "- Creative writing, brainstorming, hypotheticals, or opinion requests\n"
            "- Casual conversation or social acknowledgments\n"
            "- The question is about something already fully established in the conversation\n"
            "- Technical dev context: 'source code', 'current implementation', 'web framework', "
            "'update the config', 'state of the codebase'\n"
            "- Extremely well-known universally-agreed facts\n\n"
            "Route to WEB when the question asks about topics where the answer could be wrong, "
            "uncertain, disputed, or more current than training data.\n\n"
            "Respond with ONLY valid JSON:\n"
            '{"route": "web"|"no_web", "confidence": 0.0-1.0, "reason": "<one sentence>"}\n'
            "Return ONLY the JSON object. No markdown, no extra text."
        )

        user_prompt = (
            f"Trigger reason: {trigger_reason}\n\n"
            f"Conversation history:\n{history_block}\n\n"
            f"Latest message: {text.strip()}\n\n"
            "Does this message genuinely need live web data fetched? "
            "Consider the full context — did the trigger fire correctly or was it a false positive?"
        )

        client = OllamaClient()
        raw = client.chat(
            model=model,
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            temperature=temperature,
            num_ctx=num_ctx,
            think=False,
            timeout=timeout,
            retry_attempts=1,
            retry_backoff_sec=0.5,
            fallback_models=fallback_models,
        )
        raw = str(raw or "").strip()

        match = re.search(r"\{.*\}", raw, re.DOTALL)
        if match:
            data = json.loads(match.group())
            route = str(data.get("route", "web")).strip().lower()
            if route not in ("web", "no_web"):
                route = "web"
            confidence = float(data.get("confidence", 0.5))
            if route == "web" and confidence < _CONFIDENCE_FLOOR:
                route = "no_web"
            result = {
                "route": route,
                "confidence": confidence,
                "reason": str(data.get("reason", "")).strip()[:200],
                "skipped": False,
            }
            _emit_gate_decision(
                resolved_root,
                text=text,
                route=route,
                confidence=confidence,
                skipped=False,
                fast_path_hit=False,
                latency_ms=(time.perf_counter() - started) * 1000.0,
                reason=str(result.get("reason", "")),
            )
            return result

    except Exception as exc:
        LOGGER.debug("ChatRoutingGate LLM call failed: %s — failing open (web)", exc)

    result = {"route": "web", "confidence": 0.5, "reason": "Gate unavailable; failing open.", "skipped": False}
    _emit_gate_decision(
        resolved_root,
        text=text,
        route="web",
        confidence=0.5,
        skipped=False,
        fast_path_hit=False,
        latency_ms=(time.perf_counter() - started) * 1000.0,
        reason=result["reason"],
    )
    return result
