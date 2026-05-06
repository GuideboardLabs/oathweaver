from __future__ import annotations

import json
import shlex
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from core.kernel_commands import KernelCommandService


@dataclass(slots=True)
class TUICommandResult:
    text: str
    error: bool = False


class TUICommandRouter:
    """Slash-command router for the unified TUI interface."""

    def __init__(self, repo_root: Path) -> None:
        self.repo_root = Path(repo_root)
        self.kernel = KernelCommandService(self.repo_root)

    def dispatch(self, raw: str) -> TUICommandResult:
        text = str(raw or "").strip()
        if not text:
            return TUICommandResult("")

        if not text.startswith("/"):
            data = self.kernel.pipeline_run(text=text)
            return TUICommandResult(self._render_json(data))

        try:
            argv = shlex.split(text)
        except Exception as exc:
            return TUICommandResult(f"Command parse error: {exc}", error=True)
        cmd = argv[0].lower()
        args = argv[1:]

        try:
            if cmd == "/help":
                return TUICommandResult(self._help())
            if cmd == "/open":
                if not args:
                    return TUICommandResult("Usage: /open <project> [mode] [target] [topic_type]", error=True)
                payload = self.kernel.project_open(
                    project=args[0],
                    mode=args[1] if len(args) > 1 else "",
                    target=args[2] if len(args) > 2 else "",
                    topic_type=args[3] if len(args) > 3 else "",
                )
                return TUICommandResult(self._render_json(payload))
            if cmd == "/run":
                if not args:
                    return TUICommandResult("Usage: /run <text>", error=True)
                payload = self.kernel.pipeline_run(text=" ".join(args))
                return TUICommandResult(self._render_json(payload))
            if cmd == "/memory":
                project = args[0] if args else ""
                payload = self.kernel.memory_inspect(project=project)
                return TUICommandResult(self._render_json(payload))
            if cmd == "/audit":
                run_id = args[0] if args else ""
                payload = self.kernel.audit_report(run_id=run_id)
                return TUICommandResult(self._render_json(payload))
            if cmd == "/watchtower":
                project = args[0] if args else ""
                payload = self.kernel.watchtower_scan(project=project)
                return TUICommandResult(self._render_json(payload))
            if cmd == "/bench":
                left = args[0] if len(args) > 0 else ""
                right = args[1] if len(args) > 1 else ""
                payload = self.kernel.benchmark_compare(left_run=left, right_run=right)
                return TUICommandResult(self._render_json(payload))
            if cmd == "/bench-export":
                project = args[0] if args else ""
                payload = self.kernel.benchmark_backend_export(project=project)
                return TUICommandResult(self._render_json(payload))
            if cmd == "/bench-workflow":
                run_id = args[0] if len(args) > 0 else ""
                profile = args[1] if len(args) > 1 else "8gb_vram_16gb_ram"
                payload = self.kernel.benchmark_workflow_eval(run_id=run_id, hardware_profile=profile)
                return TUICommandResult(self._render_json(payload))
            if cmd == "/resume":
                if not args:
                    return TUICommandResult("Usage: /resume <thread_id> [from_node] [mutate_json]", error=True)
                mutate = {}
                if len(args) > 2:
                    try:
                        mutate = json.loads(args[2])
                    except Exception:
                        return TUICommandResult("mutate_json must be valid JSON object", error=True)
                payload = self.kernel.stage_resume(
                    thread_id=args[0],
                    from_node=args[1] if len(args) > 1 else "",
                    mutate=mutate if isinstance(mutate, dict) else {},
                )
                return TUICommandResult(self._render_json(payload))
            if cmd in {"/quit", "/exit"}:
                return TUICommandResult("QUIT")
        except Exception as exc:
            return TUICommandResult(f"Command failed: {exc}", error=True)

        return TUICommandResult(f"Unknown command: {cmd}. Use /help", error=True)

    @staticmethod
    def _render_json(payload: dict[str, Any]) -> str:
        return json.dumps(payload, indent=2, ensure_ascii=True)

    @staticmethod
    def _help() -> str:
        return "\n".join(
            [
                "Commands:",
                "/open <project> [mode] [target] [topic_type]",
                "/run <text>",
                "/memory [project]",
                "/audit [run_id]",
                "/watchtower [project]",
                "/bench [left_run] [right_run]",
                "/bench-export [project]",
                "/bench-workflow [run_id] [hardware_profile]",
                "/resume <thread_id> [from_node] [mutate_json]",
                "/quit",
            ]
        )
