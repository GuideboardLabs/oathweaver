from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from core.kernel_commands import KernelCommandService


def _parse_history(raw: str) -> list[dict[str, str]]:
    text = str(raw or "").strip()
    if not text:
        return []
    try:
        payload = json.loads(text)
    except Exception as exc:
        raise ValueError(f"Invalid --history-json payload: {exc}") from exc
    if not isinstance(payload, list):
        raise ValueError("--history-json must be a JSON array")
    out: list[dict[str, str]] = []
    for row in payload:
        if not isinstance(row, dict):
            continue
        role = str(row.get("role", "")).strip()
        content = str(row.get("content", "")).strip()
        if role and content:
            out.append({"role": role, "content": content})
    return out


def _parse_mutate(raw: str) -> dict[str, Any]:
    text = str(raw or "").strip()
    if not text:
        return {}
    try:
        payload = json.loads(text)
    except Exception as exc:
        raise ValueError(f"Invalid --mutate-json payload: {exc}") from exc
    if not isinstance(payload, dict):
        raise ValueError("--mutate-json must be a JSON object")
    return payload


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="oathweaver-kernel",
        description="Unified kernel CLI (Phase 10 interface layer)",
    )
    parser.add_argument("--repo-root", default=str(Path(__file__).resolve().parents[3]))
    sub = parser.add_subparsers(dest="command", required=True)

    p_open = sub.add_parser("project-open", help="Open project and optionally set mode")
    p_open.add_argument("--project", required=True)
    p_open.add_argument("--mode", default="")
    p_open.add_argument("--target", default="")
    p_open.add_argument("--topic-type", default="")

    p_run = sub.add_parser("pipeline-run", help="Run unified pipeline turn")
    p_run.add_argument("--text", required=True)
    p_run.add_argument("--history-json", default="")
    p_run.add_argument("--thread-id", default="")
    p_run.add_argument("--force-research", action="store_true")
    p_run.add_argument("--force-make", action="store_true")
    p_run.add_argument("--hardware-profile", default="")

    p_mem = sub.add_parser("memory-inspect", help="Inspect CAG memory rows")
    p_mem.add_argument("--project", default="")
    p_mem.add_argument("--limit", type=int, default=40)

    p_audit = sub.add_parser("audit-report", help="Read auditor regression report")
    p_audit.add_argument("--run-id", default="")

    p_scan = sub.add_parser("watchtower-scan", help="Run watchtower project gap scan")
    p_scan.add_argument("--project", default="")

    p_bench = sub.add_parser("benchmark-compare", help="Compare two benchmark runs")
    p_bench.add_argument("--left-run", default="")
    p_bench.add_argument("--right-run", default="")

    p_bench_export = sub.add_parser("benchmark-backend-export", help="Export CAG memory in cag-bench backend shape")
    p_bench_export.add_argument("--project", default="")
    p_bench_export.add_argument("--limit", type=int, default=500)

    p_workflow = sub.add_parser("benchmark-workflow-eval", help="Evaluate phase-12 workflow benchmark gate")
    p_workflow.add_argument("--run-id", default="")
    p_workflow.add_argument("--hardware-profile", default="8gb_vram_16gb_ram")

    p_resume = sub.add_parser("stage-resume", help="Resume/replay from saved turn checkpoint")
    p_resume.add_argument("--thread-id", required=True)
    p_resume.add_argument("--from-node", default="")
    p_resume.add_argument("--mutate-json", default="")

    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()
    repo_root = Path(str(args.repo_root)).resolve()
    service = KernelCommandService(repo_root)

    try:
        if args.command == "project-open":
            payload = service.project_open(project=args.project, mode=args.mode, target=args.target, topic_type=args.topic_type)
        elif args.command == "pipeline-run":
            payload = service.pipeline_run(
                text=args.text,
                history=_parse_history(args.history_json),
                thread_id=args.thread_id,
                force_research=bool(args.force_research),
                force_make=bool(args.force_make),
                hardware_profile=args.hardware_profile,
            )
        elif args.command == "memory-inspect":
            payload = service.memory_inspect(project=args.project, limit=int(args.limit))
        elif args.command == "audit-report":
            payload = service.audit_report(run_id=args.run_id)
        elif args.command == "watchtower-scan":
            payload = service.watchtower_scan(project=args.project)
        elif args.command == "benchmark-compare":
            payload = service.benchmark_compare(left_run=args.left_run, right_run=args.right_run)
        elif args.command == "benchmark-backend-export":
            payload = service.benchmark_backend_export(project=args.project, limit=int(args.limit))
        elif args.command == "benchmark-workflow-eval":
            payload = service.benchmark_workflow_eval(run_id=args.run_id, hardware_profile=args.hardware_profile)
        elif args.command == "stage-resume":
            payload = service.stage_resume(thread_id=args.thread_id, from_node=args.from_node, mutate=_parse_mutate(args.mutate_json))
        else:
            payload = {"ok": False, "error": f"Unknown command: {args.command}"}
    except Exception as exc:
        payload = {"ok": False, "error": str(exc)}

    print(json.dumps(payload, indent=2, ensure_ascii=True))


if __name__ == "__main__":
    main()
