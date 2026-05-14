#!/usr/bin/env python3
"""
Oathweaver Benchmark Runner
============================
Runs a fixed set of research questions through run_research_pool and reports
wall-clock timing, per-agent elapsed time, reliability, and synthesis quality.

Usage (from e:\\Oathweaver\\SourceCode):
    python -m benchmark.run              # full suite (~8 questions)
    python -m benchmark.run --quick      # first 2 questions only
    python -m benchmark.run --target sports
    python -m benchmark.run --id tech_01
    python -m benchmark.run --out my_results.json

Results are saved to Runtime/benchmark/results_TIMESTAMP.json after each
question (incremental save — safe to Ctrl+C and review partial results).
"""

import argparse
import json
import subprocess
import sys
import threading
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

# ---------------------------------------------------------------------------
# Path setup — works whether run as `python -m benchmark.run` from SourceCode
# or as `python SourceCode/benchmark/run.py` from the repo root.
# ---------------------------------------------------------------------------
_HERE = Path(__file__).resolve()
_SOURCECODE = _HERE.parents[1]
_REPO_ROOT = _HERE.parents[2]
sys.path.insert(0, str(_SOURCECODE))

from agents_research.deep_researcher import run_research_pool  # noqa: E402
from agents_research.synthesizer import _is_valid_synthesis  # noqa: E402
from core.capability_registry import CapabilityRegistry  # noqa: E402

# ---------------------------------------------------------------------------
# Question suite
# ---------------------------------------------------------------------------
BENCHMARK_QUESTIONS: list[dict[str, str]] = [
    {
        "id": "gen_01",
        "question": "What are the main factors driving current global inflation trends and how are central banks responding?",
        "target": "general",
        "expected_profile": "general_analysis",
        "category": "Current events / economics",
    },
    {
        "id": "gen_02",
        "question": "What is the current state of nuclear fusion energy development and what are realistic timelines to commercial viability?",
        "target": "general",
        "expected_profile": "general_analysis",
        "category": "Science / current events",
    },
    {
        "id": "tech_01",
        "question": "What are the architectural trade-offs between WebSockets and Server-Sent Events for a real-time notification system?",
        "target": "web_app",
        "expected_profile": "technical_analysis",
        "category": "Technical / web",
    },
    {
        "id": "tech_02",
        "question": "What are the key risks and mitigation strategies when migrating a monolithic Python Flask app to microservices?",
        "target": "web_app",
        "expected_profile": "technical_analysis",
        "category": "Technical / architecture",
    },
    {
        "id": "sport_01",
        "question": "What are the dominant tactical trends in modern football high-press systems and which clubs execute them most effectively?",
        "target": "sports",
        "expected_profile": "sports_analysis",
        "category": "Sports / football",
    },
    {
        "id": "hist_01",
        "question": "What were the primary economic, military, and political causes of the fall of the Western Roman Empire?",
        "target": "history",
        "expected_profile": "history_analysis",
        "category": "History",
    },
    {
        "id": "med_01",
        "question": "What does current evidence say about the effectiveness and safety of intermittent fasting for metabolic health?",
        "target": "medical",
        "expected_profile": "medical_analysis",
        "category": "Medical / nutrition",
    },
    {
        "id": "fin_01",
        "question": "What are the main macro risks facing global equity markets and how should a conservative long-term portfolio respond?",
        "target": "finance",
        "expected_profile": "finance_analysis",
        "category": "Finance / macro",
    },
]

EXPECTED_SECTIONS = [
    "executive summary",
    "what we know",
    "disagreements/uncertainty",
    "risks",
    "follow-up questions",
    "actionable next steps",
]

PROJECT_SLUG = "benchmark"


# ---------------------------------------------------------------------------
# Silent bus — keeps benchmark runs out of the main activity log
# ---------------------------------------------------------------------------
class _NullBus:
    def emit(self, actor: str, event: str, details: dict | None = None) -> None:
        pass


# ---------------------------------------------------------------------------
# Resource monitoring (RAM via psutil, GPU via rocm-smi / nvidia-smi)
# ---------------------------------------------------------------------------
try:
    import psutil as _psutil_mod  # type: ignore[import]
    _PSUTIL = True
except ImportError:
    _psutil_mod = None  # type: ignore[assignment]
    _PSUTIL = False


def _ram_rss_mb() -> float | None:
    if not _PSUTIL or _psutil_mod is None:
        return None
    try:
        return _psutil_mod.Process().memory_info().rss / (1024 * 1024)
    except Exception:
        return None


def _gpu_vram_used_mb() -> float | None:
    """Try rocm-smi (AMD RX 5700 XT) then nvidia-smi. Returns used VRAM in MB."""
    # AMD ROCm
    try:
        r = subprocess.run(
            ["rocm-smi", "--showmeminfo", "vram", "--json"],
            capture_output=True, text=True, timeout=5,
        )
        if r.returncode == 0 and r.stdout.strip():
            data = json.loads(r.stdout)
            for card in data.values():
                if isinstance(card, dict):
                    for k, v in card.items():
                        if "used" in k.lower() and "vram" in k.lower():
                            return int(v) / (1024 * 1024)
    except Exception:
        pass
    # NVIDIA fallback
    try:
        r = subprocess.run(
            ["nvidia-smi", "--query-gpu=memory.used", "--format=csv,noheader,nounits"],
            capture_output=True, text=True, timeout=5,
        )
        if r.returncode == 0 and r.stdout.strip():
            return float(r.stdout.strip().split("\n")[0])
    except Exception:
        pass
    return None


class _ResourcePoller:
    """Polls RAM and GPU VRAM every 2 seconds in a background thread."""

    def __init__(self) -> None:
        self.peak_ram_mb: float = 0.0
        self.peak_gpu_mb: float = 0.0
        self._stop = threading.Event()
        self._thread = threading.Thread(target=self._poll, daemon=True)

    def start(self) -> None:
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()
        self._thread.join(timeout=6)

    def _poll(self) -> None:
        while not self._stop.is_set():
            ram = _ram_rss_mb()
            if ram is not None and ram > self.peak_ram_mb:
                self.peak_ram_mb = ram
            gpu = _gpu_vram_used_mb()
            if gpu is not None and gpu > self.peak_gpu_mb:
                self.peak_gpu_mb = gpu
            self._stop.wait(2.0)


# ---------------------------------------------------------------------------
# Single question run
# ---------------------------------------------------------------------------
def _run_question(spec: dict[str, str], repo_root: Path) -> dict[str, Any]:
    bus = _NullBus()
    agent_start_times: dict[str, float] = {}
    agent_timings: list[dict[str, Any]] = []
    pool_started_at: list[float] = [0.0]  # list to allow mutation from nested fn

    def _progress_cb(stage: str, detail: Any = None) -> None:
        now = time.perf_counter()
        if stage == "research_pool_started":
            pool_started_at[0] = now
        elif stage == "research_agent_started" and isinstance(detail, dict):
            persona = str(detail.get("agent", "")).strip()
            if persona:
                agent_start_times[persona] = now
        elif stage == "research_agent_completed" and isinstance(detail, dict):
            persona = str(detail.get("agent", "")).strip()
            start = agent_start_times.pop(persona, now)
            agent_timings.append({
                "persona": persona,
                "elapsed_sec": round(now - start, 2),
                "role": str(detail.get("role", "primary")),
                "failed": bool(detail.get("failed", False)),
            })

    poller = _ResourcePoller()
    poller.start()
    t_start = time.perf_counter()

    try:
        result: dict[str, Any] = run_research_pool(
            spec["question"],
            repo_root,
            PROJECT_SLUG,
            bus,
            progress_callback=_progress_cb,
            topic_type=spec.get("topic_type", spec.get("target", "general")),
        )
    except Exception as exc:
        result = {
            "message": f"Exception: {exc}",
            "summary_path": "",
            "raw_path": "",
            "reliability": {"good": 0, "weak": 0, "failed": 0, "agents_total": 0},
            "analysis_profile": spec.get("expected_profile", ""),
            "canceled": False,
        }

    t_end = time.perf_counter()
    poller.stop()

    # Read synthesis to assess quality
    summary_path = str(result.get("summary_path", "")).strip()
    synthesis_text = ""
    if summary_path:
        try:
            synthesis_text = Path(summary_path).read_text(encoding="utf-8")
        except Exception:
            pass

    sections_found = sum(1 for s in EXPECTED_SECTIONS if s in synthesis_text.lower())
    synthesis_valid = _is_valid_synthesis(synthesis_text)

    actual_profile = str(result.get("analysis_profile", "")).strip()

    return {
        "id": spec["id"],
        "question": spec["question"],
        "target": spec["target"],
        "category": spec.get("category", ""),
        "expected_profile": spec.get("expected_profile", ""),
        "actual_profile": actual_profile,
        "profile_matched": spec.get("expected_profile", "") == actual_profile,
        "total_elapsed_sec": round(t_end - t_start, 2),
        "pool_overhead_sec": round(pool_started_at[0] - t_start, 2) if pool_started_at[0] else None,
        "reliability": result.get("reliability", {}),
        "synthesis_valid": synthesis_valid,
        "synthesis_sections_found": sections_found,
        "synthesis_sections_total": len(EXPECTED_SECTIONS),
        "synthesis_length_chars": len(synthesis_text),
        "agent_timings": sorted(agent_timings, key=lambda x: x["elapsed_sec"], reverse=True),
        "summary_path": summary_path,
        "raw_path": str(result.get("raw_path", "")),
        "canceled": bool(result.get("canceled", False)),
        "peak_ram_mb": round(poller.peak_ram_mb, 1) if poller.peak_ram_mb else None,
        "peak_gpu_mb": round(poller.peak_gpu_mb, 1) if poller.peak_gpu_mb else None,
    }


# ---------------------------------------------------------------------------
# Formatting helpers
# ---------------------------------------------------------------------------
def _fmt_sec(sec: float) -> str:
    if sec < 60:
        return f"{sec:.1f}s"
    return f"{int(sec // 60)}m{sec % 60:.0f}s"


def _rel_str(rel: dict) -> str:
    g = int(rel.get("good", 0))
    w = int(rel.get("weak", 0))
    f = int(rel.get("failed", 0))
    return f"{g}g/{w}w/{f}f"


def _print_summary(results: list[dict[str, Any]]) -> None:
    print()
    print("=" * 88)


def _benchmark_capability_score(results: list[dict[str, Any]]) -> float:
    if not results:
        return 0.0
    quality_terms: list[float] = []
    for row in results:
        rel = row.get("reliability", {}) if isinstance(row.get("reliability", {}), dict) else {}
        good = float(rel.get("good", 0) or 0)
        weak = float(rel.get("weak", 0) or 0)
        failed = float(rel.get("failed", 0) or 0)
        total = max(1.0, good + weak + failed)
        reliability_score = max(0.0, min(1.0, (good + (0.5 * weak)) / total))
        synth_score = 1.0 if bool(row.get("synthesis_valid", False)) else 0.0
        section_found = float(row.get("synthesis_sections_found", 0) or 0)
        section_total = max(1.0, float(row.get("synthesis_sections_total", 1) or 1))
        coverage_score = max(0.0, min(1.0, section_found / section_total))
        quality_terms.append((0.5 * reliability_score) + (0.35 * synth_score) + (0.15 * coverage_score))
    return round(sum(quality_terms) / len(quality_terms), 4)
    print("  GUIDEBOARD BENCHMARK RESULTS")
    print(f"  {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 88)

    if not results:
        print("  No results to display.")
        return

    col_id  = max(8,  max(len(r["id"])     for r in results))
    col_tgt = max(10, max(len(r["target"])  for r in results))
    col_cat = max(8,  max(len(r.get("category", "")) for r in results))

    hdr = (
        f"  {'ID':<{col_id}}  {'TARGET':<{col_tgt}}  {'CATEGORY':<{col_cat}}"
        f"  {'TIME':>8}  {'AGENTS':>9}  {'SYNTH':>5}  {'SECTS':>5}  {'CHARS':>6}"
    )
    print(hdr)
    print("  " + "-" * (len(hdr) - 2))

    total_elapsed = 0.0
    total_good = total_weak = total_failed = 0

    for r in results:
        rel = r.get("reliability", {})
        g = int(rel.get("good", 0))
        w = int(rel.get("weak", 0))
        f = int(rel.get("failed", 0))
        total_good += g
        total_weak += w
        total_failed += f
        elapsed = float(r.get("total_elapsed_sec", 0))
        total_elapsed += elapsed
        synth = "PASS" if r.get("synthesis_valid") else "FAIL"
        sects = f"{r.get('synthesis_sections_found', 0)}/{r.get('synthesis_sections_total', 0)}"
        chars = str(r.get("synthesis_length_chars", 0))
        cancel = " [CANCELLED]" if r.get("canceled") else ""
        profile_warn = " (!profile)" if not r.get("profile_matched", True) else ""

        print(
            f"  {r['id']:<{col_id}}  {r['target']:<{col_tgt}}  {r.get('category', ''):<{col_cat}}"
            f"  {_fmt_sec(elapsed):>8}  {_rel_str(rel):>9}  {synth:>5}  {sects:>5}  {chars:>6}"
            f"{cancel}{profile_warn}"
        )

    print("  " + "-" * (len(hdr) - 2))
    print(
        f"  TOTAL: {_fmt_sec(total_elapsed)}"
        f"  |  All agents: {total_good}g / {total_weak}w / {total_failed}f"
        f"  |  Questions: {len(results)}"
    )

    slowest = max(results, key=lambda r: float(r.get("total_elapsed_sec", 0)))
    fastest = min(results, key=lambda r: float(r.get("total_elapsed_sec", 0)))
    print(f"  Slowest: {slowest['id']} ({_fmt_sec(float(slowest['total_elapsed_sec']))})"
          f"   Fastest: {fastest['id']} ({_fmt_sec(float(fastest['total_elapsed_sec']))})")

    # Agent timing breakdown
    all_agents: dict[str, list[float]] = {}
    for r in results:
        for at in r.get("agent_timings", []):
            persona = str(at.get("persona", ""))
            if persona:
                all_agents.setdefault(persona, []).append(float(at.get("elapsed_sec", 0)))

    if all_agents:
        print()
        print("  Agent elapsed time averages (slowest first):")
        for persona, times in sorted(all_agents.items(), key=lambda x: -(sum(x[1]) / len(x[1]))):
            avg = sum(times) / len(times)
            fastest_t = min(times)
            slowest_t = max(times)
            n = len(times)
            print(
                f"    {persona:<38} avg {_fmt_sec(avg):>7}"
                f"  min {_fmt_sec(fastest_t):>7}  max {_fmt_sec(slowest_t):>7}  (n={n})"
            )

    # Resource stats
    rams = [r["peak_ram_mb"] for r in results if r.get("peak_ram_mb")]
    gpus = [r["peak_gpu_mb"] for r in results if r.get("peak_gpu_mb")]
    print()
    if rams:
        print(f"  Peak RAM:  min={min(rams):.0f}MB  max={max(rams):.0f}MB  avg={sum(rams)/len(rams):.0f}MB")
    else:
        print("  RAM monitoring: unavailable (pip install psutil to enable)")
    if gpus:
        print(f"  Peak VRAM: min={min(gpus):.0f}MB  max={max(gpus):.0f}MB  avg={sum(gpus)/len(gpus):.0f}MB")
    else:
        print("  VRAM monitoring: unavailable (rocm-smi / nvidia-smi not found in PATH)")

    print("=" * 88)


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------
def main() -> None:
    parser = argparse.ArgumentParser(
        description="Oathweaver benchmark runner — measures timing, reliability, and synthesis quality",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument("--quick", action="store_true", help="Run only the first 2 questions (fast sanity check)")
    parser.add_argument("--target", help="Run only questions for this delivery target (e.g. 'general', 'sports')")
    parser.add_argument("--id", dest="question_id", help="Run a single question by ID (e.g. 'tech_01')")
    parser.add_argument("--out", help="Custom output path for JSON results file")
    parser.add_argument("--list", action="store_true", help="List all benchmark questions and exit")
    args = parser.parse_args()

    if args.list:
        print(f"{'ID':<10}  {'TARGET':<12}  QUESTION")
        print("-" * 80)
        for q in BENCHMARK_QUESTIONS:
            print(f"{q['id']:<10}  {q['target']:<12}  {q['question'][:60]}")
        return

    questions = list(BENCHMARK_QUESTIONS)
    if args.question_id:
        questions = [q for q in questions if q["id"] == args.question_id]
        if not questions:
            print(f"Error: No question found with id '{args.question_id}'")
            print(f"Available IDs: {', '.join(q['id'] for q in BENCHMARK_QUESTIONS)}")
            sys.exit(1)
    elif args.target:
        questions = [q for q in questions if q["target"] == args.target]
        if not questions:
            print(f"Error: No questions for target '{args.target}'")
            print(f"Available targets: {', '.join(sorted({q['target'] for q in BENCHMARK_QUESTIONS}))}")
            sys.exit(1)
    elif args.quick:
        questions = questions[:2]

    repo_root = _REPO_ROOT
    ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    out_dir = repo_root / "Runtime" / "benchmark"
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = Path(args.out) if args.out else out_dir / f"results_{ts}.json"

    print()
    print("  Oathweaver Benchmark Runner")
    print(f"  Questions to run : {len(questions)}")
    print(f"  Repo root        : {repo_root}")
    print(f"  Results file     : {out_path}")
    print(f"  psutil (RAM)     : {'yes' if _PSUTIL else 'no — pip install psutil to enable'}")
    gpu_check = _gpu_vram_used_mb()
    print(f"  GPU monitor      : {'yes — ' + str(int(gpu_check)) + 'MB used now' if gpu_check is not None else 'no — rocm-smi/nvidia-smi not found'}")
    print()

    results: list[dict[str, Any]] = []
    benchmark_meta: dict[str, Any] = {
        "timestamp": ts,
        "repo_root": str(repo_root),
        "psutil_available": _PSUTIL,
        "gpu_monitor_available": gpu_check is not None,
    }

    for i, spec in enumerate(questions, 1):
        print(f"  [{i}/{len(questions)}] {spec['id']}  target={spec['target']}")
        print(f"         {spec['question'][:75]}")
        result = _run_question(spec, repo_root)
        rel = result.get("reliability", {})
        elapsed = float(result.get("total_elapsed_sec", 0))
        synth = "PASS" if result["synthesis_valid"] else "FAIL"
        ram_note = f"  RAM={result['peak_ram_mb']:.0f}MB" if result.get("peak_ram_mb") else ""
        gpu_note = f"  VRAM={result['peak_gpu_mb']:.0f}MB" if result.get("peak_gpu_mb") else ""
        print(f"         done {_fmt_sec(elapsed)}  agents {_rel_str(rel)}  synth {synth}{ram_note}{gpu_note}")
        print()

        results.append(result)
        # Incremental save after each question
        out_path.write_text(
            json.dumps({**benchmark_meta, "results": results}, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )

    _print_summary(results)
    try:
        registry = CapabilityRegistry(repo_root)
        capability_score = _benchmark_capability_score(results)
        registry.record_run_observation(
            claim_text="8B + CAG + pipeline can approach 70B quality on long-running architecture work",
            run_id=f"benchmark_{ts}",
            pipeline="benchmark.run",
            final_score=float(capability_score),
            benchmark_id="benchmark_run_v1",
            status="hypothesis",
        )
    except Exception as exc:
        print(f"  [warn] capability registry update skipped: {exc}")
    print(f"\n  Full results: {out_path}\n")


if __name__ == "__main__":
    main()
