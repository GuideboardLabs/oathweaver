#!/usr/bin/env python3
"""
Routing smoke test — runs prompts through chat, research, or make lanes
using a small fast model. Tests routing and pipeline wiring, not quality.

Usage:
    python scripts/routing_smoke.py --list-types

    python scripts/routing_smoke.py --mode chat
    python scripts/routing_smoke.py --mode research
    python scripts/routing_smoke.py --mode make --make-type blog
    python scripts/routing_smoke.py --mode make --make-type tool --prompt "count files in a dir"

    python scripts/routing_smoke.py --all          # run every lane
    python scripts/routing_smoke.py --all --model phi4-mini:3.8b
"""
from __future__ import annotations

import argparse
import sys
import time
import traceback
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "SourceCode"
sys.path.insert(0, str(SOURCE))
sys.path.insert(0, str(ROOT))

from tests.common import ensure_runtime  # noqa: E402

SMALL_MODEL = "qwen3:4b"

# ---------------------------------------------------------------------------
# Canned prompts per lane / make-type
# ---------------------------------------------------------------------------
CHAT_PROMPT     = "What are three practical tips for staying focused while working from home?"
RESEARCH_PROMPT = "What are the main trade-offs between SSDs and HDDs for a home server in 2025?"

MAKE_PROMPTS: dict[str, str] = {
    "tool":           "Write a Python script that counts lines of code in a directory.",
    "web_app":        "Build a simple todo list web app with Flask and Vue 3.",
    "desktop_app":    "Build a basic note-taking desktop app with .NET 8 and Avalonia.",
    "social_post":    "Write a LinkedIn post about the benefits of daily walks.",
    "email":          "Write a professional follow-up email after a job interview.",
    "blog":           "Write a blog post about why sleep is underrated for productivity.",
    "essay_short":    "Write a short essay on why constraints make better creative work.",
    "essay_long":     "Write a long-form essay on how the internet changed attention spans.",
    "guide":          "Write a guide on setting up a Python virtual environment.",
    "tutorial":       "Write a tutorial on how to use Git branches effectively.",
    "video_script":   "Write a video script explaining how black holes form.",
    "newsletter":     "Write a newsletter edition about trends in remote work.",
    "press_release":  "Write a press release announcing a new project management tool.",
    "novel_chapter":  "Write the opening chapter of a thriller set in Tokyo.",
    "memoir_chapter": "Write a memoir chapter about learning to ride a bike as a child.",
    "book_chapter":   "Write a non-fiction book chapter on the psychology of habits.",
    "screenplay":     "Write the opening scene of a screenplay set in a 1950s diner.",
    "medical":        "Write a clinical summary on the current evidence for intermittent fasting.",
    "finance":        "Write a financial analysis of the renewable energy sector.",
    "sports":         "Write a statistical analysis of the NBA three-point shooting trend.",
    "history":        "Write an essay on the causes of the fall of the Roman Empire.",
    "game_design_doc":"Write a game design document for a turn-based strategy roguelike.",
}


# ---------------------------------------------------------------------------
# Routing config — small model everywhere, no premium gates
# no_limits=True removes all timeouts and raises context for big slow models
# ---------------------------------------------------------------------------
def _fast_routing(model: str, no_limits: bool = False) -> dict:
    timeout = 86400 if no_limits else 60
    ctx     = 16384 if no_limits else 2048
    tier = {
        "model": model,
        "temperature": 0.1,
        "num_ctx": ctx,
        "timeout_sec": timeout,
        "retry_attempts": 1,
        "retry_backoff_sec": 0.5,
        "fallback_models": [],
    }
    return {
        "chat_layer":         {**tier, "purpose": "smoke"},
        "conversation_layer": {**tier, "purpose": "smoke"},
        "orchestrator_reasoning": {
            **tier, "purpose": "smoke",
            "synthesis_timeout_sec": timeout, "synthesis_retry_attempts": 1,
            "synthesis_retry_backoff_sec": 0.5, "synthesis_validation_cycles": 1,
            "synthesis_fallback_models": [],
            "reflection_gate_open_limit": 0,
            "reflection_temperature": 0.1, "reflection_num_ctx": ctx,
            "reflection_timeout_sec": timeout,
        },
        "make_content":    {**tier, "purpose": "smoke"},
        "make_longform":   {**tier, "purpose": "smoke"},
        "make_creative":   {**tier, "purpose": "smoke"},
        "make_specialist": {**tier, "purpose": "smoke"},
        "make_tool":       {**tier, "purpose": "smoke"},
        "make_desktop_app":{**tier, "purpose": "smoke"},
        "make_app":        {**tier, "purpose": "smoke"},
        "research_pool": {
            **tier, "purpose": "smoke", "parallel_agents": 1,
            "validation_cycles": 1, "gap_fill_enabled": False,
            "draft_critique_revise": {"enabled": False},
            "fallback_models": [], "agent_mix": [],
        },
        "synthesis": {
            **tier, "purpose": "smoke",
            "synthesis_retry_attempts": 1, "synthesis_validation_cycles": 1,
            "synthesis_retry_backoff_sec": 0.5, "synthesis_fallback_models": [],
            "tier_default": tier, "tier_premium": tier,
            "escalation_policy": {"enabled": False},
        },
        "embeddings":       {"provider": "ollama", "model": model},
        "intent_confirmer": {**tier, "purpose": "smoke"},
        "chat_routing_gate":{**tier, "purpose": "smoke", "temperature": 0.0},
        "ui_pool":          {**tier, "purpose": "smoke", "parallel_agents": 1},
        "premium_models": [],
        "orchestrator.chat_via_graph": True,
        "orchestrator.checkpoint_retention_days": 1,
        "make_type_classifier.enabled": True,
        "make_type_classifier.confidence_threshold": 0.5,
        "research_pool.max_handoffs": 1,
        "research.citation_cosine_threshold": 0.45,
        "mcp.http_enabled": False,
        "mcp.use_fetch": False,
        "mcp.acknowledge_unsafe_http": False,
    }


# ---------------------------------------------------------------------------
# Individual lane runners
# ---------------------------------------------------------------------------
def _run_chat(orch: object, prompt: str, on_progress) -> str:
    return orch.conversation_reply(  # type: ignore[attr-defined]
        prompt,
        history=[],
        progress_callback=on_progress,
    )


def _run_research(orch: object, prompt: str, on_progress) -> str:
    return orch.handle_message(  # type: ignore[attr-defined]
        prompt,
        history=[],
        project_mode={"mode": "discovery", "target": "auto", "topic_type": "general"},
        force_research=True,
        progress_callback=on_progress,
    )


def _run_make(orch: object, prompt: str, make_type: str, on_progress) -> str:
    return orch.handle_message(  # type: ignore[attr-defined]
        prompt,
        history=[],
        project_mode={"mode": "make", "target": make_type, "topic_type": "general"},
        force_make=True,
        progress_callback=on_progress,
    )


# ---------------------------------------------------------------------------
# Single test case
# ---------------------------------------------------------------------------
def run_one(
    label: str,
    prompt: str,
    runner,          # callable(orch, prompt, on_progress) -> str
    model: str,
    verbose: bool = True,
    no_limits: bool = False,
) -> dict:
    """Run one lane and return a result dict."""
    routing = _fast_routing(model, no_limits=no_limits)
    stages: list[tuple[str, str]] = []
    t0 = time.monotonic()

    def on_progress(stage: str, detail: str = "") -> None:
        elapsed = time.monotonic() - t0
        stages.append((stage, detail))
        if verbose:
            detail_short = (detail or "")[:60]
            print(f"  [{elapsed:5.1f}s] {stage:<30} {detail_short}")

    if verbose:
        print(f"\n{'='*60}")
        print(f"  {label}")
        print(f"  Model : {model}")
        print(f"  Prompt: {prompt[:80]}{'...' if len(prompt) > 80 else ''}")
        print(f"{'='*60}\n")

    err = ""
    tb = ""
    reply = ""
    try:
        with patch("shared_tools.model_routing.load_model_routing", return_value=routing), \
             patch("orchestrator.main.load_model_routing", return_value=routing):

            from orchestrator.main import OathweaverOrchestrator
            orch = OathweaverOrchestrator(ROOT)
            orch.project_slug = "general"
            t0 = time.monotonic()
            reply = runner(orch, prompt, on_progress)

    except Exception as exc:
        err = str(exc)
        tb = traceback.format_exc()

    elapsed = time.monotonic() - t0
    detected_routing = next((d for _, d in stages if "Pipeline:" in d), "")
    passed = bool(reply) and not err

    if verbose:
        status = "PASS" if passed else "FAIL"
        print(f"\n  {status}  {elapsed:.1f}s  {detected_routing}")
        if err:
            print(f"\n  ERROR: {err}\n")
            print("  --- Traceback ---")
            for line in tb.splitlines():
                print(f"  {line}")
            print()
        elif reply:
            print(f"  Reply: {reply[:160]}{'...' if len(reply) > 160 else ''}")
        print()

    return {
        "label": label,
        "passed": passed,
        "elapsed": elapsed,
        "routing": detected_routing,
        "error": err,
        "traceback": tb,
        "stages": len(stages),
    }


# ---------------------------------------------------------------------------
# Print helpers
# ---------------------------------------------------------------------------
def _print_types() -> None:
    from orchestrator.services.make_catalog import MAKE_CATALOG
    by_lane: dict[str, list[tuple[str, str]]] = {}
    for tid, entry in MAKE_CATALOG.items():
        by_lane.setdefault(entry["lane"], []).append((tid, entry["label"]))
    print("\nAvailable --make-type values:\n")
    for lane in sorted(by_lane):
        print(f"  {lane}")
        for tid, label in sorted(by_lane[lane]):
            print(f"    {tid:<22}  {label}")
    print()


def _print_summary(results: list[dict]) -> None:
    passed = [r for r in results if r["passed"]]
    failed = [r for r in results if not r["passed"]]
    print(f"\n{'='*60}")
    print(f"  SUMMARY  {len(passed)}/{len(results)} passed\n")
    col = 28
    for r in results:
        icon = "✓" if r["passed"] else "✗"
        label = r["label"][:col].ljust(col)
        elapsed = f"{r['elapsed']:5.1f}s"
        print(f"  {icon}  {label}  {elapsed}")
    if failed:
        print(f"\n{'='*60}")
        print(f"  FAILURES\n")
        for r in failed:
            print(f"  ✗  {r['label']}")
            print(f"     Error: {r['error']}")
            if r.get("traceback"):
                print()
                for line in r["traceback"].splitlines():
                    print(f"     {line}")
            print()
    print(f"{'='*60}\n")
    if failed:
        sys.exit(1)


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------
def main() -> None:
    parser = argparse.ArgumentParser(description="Lane routing smoke test")
    parser.add_argument("--list-types", action="store_true",
                        help="Print all make types and exit")
    parser.add_argument("--mode", choices=["chat", "research", "make"],
                        help="Lane to test: chat, research, or make")
    parser.add_argument("--make-type", metavar="TYPE",
                        help="Make type id (e.g. blog, tool, email). Required with --mode make.")
    parser.add_argument("--prompt", default="",
                        help="Override the default canned prompt")
    parser.add_argument("--model", default=SMALL_MODEL,
                        help=f"Ollama model (default: {SMALL_MODEL})")
    parser.add_argument("--all", action="store_true",
                        help="Run chat, research, and every make type")
    parser.add_argument("--no-limits", action="store_true",
                        help="Remove all timeouts and raise context window — use with large slow models")
    args = parser.parse_args()

    ensure_runtime(ROOT)

    if args.list_types:
        _print_types()
        return

    nl = args.no_limits

    if args.all:
        from orchestrator.services.make_catalog import MAKE_CATALOG, label_for_type
        results: list[dict] = []
        results.append(run_one("chat", args.prompt or CHAT_PROMPT,
                               _run_chat, args.model, verbose=False, no_limits=nl))
        results.append(run_one("research", args.prompt or RESEARCH_PROMPT,
                               _run_research, args.model, verbose=False, no_limits=nl))
        for tid in sorted(MAKE_CATALOG):
            label = f"make:{tid} ({label_for_type(tid)})"
            prompt = args.prompt or MAKE_PROMPTS.get(tid, f"Write a {label_for_type(tid).lower()}.")
            results.append(run_one(label, prompt,
                                   lambda o, p, cb, t=tid: _run_make(o, p, t, cb),
                                   args.model, verbose=False, no_limits=nl))
            r = results[-1]
            icon = "✓" if r["passed"] else "✗"
            print(f"  {icon}  {r['label'][:50]:<50}  {r['elapsed']:.1f}s"
                  + (f"  ERR: {r['error'][:40]}" if r["error"] else ""))
        _print_summary(results)
        return

    if args.mode == "chat":
        r = run_one("chat", args.prompt or CHAT_PROMPT, _run_chat, args.model, no_limits=nl)
    elif args.mode == "research":
        r = run_one("research", args.prompt or RESEARCH_PROMPT, _run_research, args.model, no_limits=nl)
    elif args.mode == "make":
        if not args.make_type:
            parser.error("--make-type is required with --mode make")
        from orchestrator.services.make_catalog import MAKE_CATALOG, label_for_type
        if args.make_type not in MAKE_CATALOG:
            print(f"Unknown make type '{args.make_type}'. Run --list-types to see options.")
            sys.exit(1)
        prompt = args.prompt or MAKE_PROMPTS.get(args.make_type, f"Write a {label_for_type(args.make_type).lower()}.")
        label = f"make:{args.make_type} — {label_for_type(args.make_type)}"
        mt = args.make_type
        r = run_one(label, prompt, lambda o, p, cb: _run_make(o, p, mt, cb), args.model, no_limits=nl)
    else:
        parser.print_help()
        return

    sys.exit(0 if r["passed"] else 1)


if __name__ == "__main__":
    main()
