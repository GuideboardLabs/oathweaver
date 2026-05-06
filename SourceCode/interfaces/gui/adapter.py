from __future__ import annotations

from pathlib import Path
from typing import Any

from core.kernel_commands import KernelCommandService


class GUIKernelAdapter:
    """Thin bridge used by GUI handlers to call kernel commands."""

    def __init__(self, repo_root: Path, *, service: KernelCommandService | None = None) -> None:
        self.repo_root = Path(repo_root)
        self.service = service or KernelCommandService(self.repo_root)

    def open_project(self, *, project: str, mode: str = "", target: str = "", topic_type: str = "") -> dict[str, Any]:
        return self.service.project_open(project=project, mode=mode, target=target, topic_type=topic_type)

    def run_pipeline(self, *, text: str, history: list[dict[str, str]] | None = None, thread_id: str = "") -> dict[str, Any]:
        return self.service.pipeline_run(text=text, history=history, thread_id=thread_id)

    def inspect_memory(self, *, project: str = "", limit: int = 40) -> dict[str, Any]:
        return self.service.memory_inspect(project=project, limit=limit)

    def latest_audit(self, *, run_id: str = "") -> dict[str, Any]:
        return self.service.audit_report(run_id=run_id)

    def run_watchtower_scan(self, *, project: str = "") -> dict[str, Any]:
        return self.service.watchtower_scan(project=project)

    def compare_benchmarks(self, *, left_run: str = "", right_run: str = "") -> dict[str, Any]:
        return self.service.benchmark_compare(left_run=left_run, right_run=right_run)

    def export_benchmark_backend(self, *, project: str = "", limit: int = 500) -> dict[str, Any]:
        return self.service.benchmark_backend_export(project=project, limit=limit)

    def evaluate_benchmark_workflow(self, *, run_id: str = "", hardware_profile: str = "8gb_vram_16gb_ram") -> dict[str, Any]:
        return self.service.benchmark_workflow_eval(run_id=run_id, hardware_profile=hardware_profile)

    def resume_stage(self, *, thread_id: str, from_node: str = "", mutate: dict[str, Any] | None = None) -> dict[str, Any]:
        return self.service.stage_resume(thread_id=thread_id, from_node=from_node, mutate=mutate)
