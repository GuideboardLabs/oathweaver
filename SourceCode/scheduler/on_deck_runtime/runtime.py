from __future__ import annotations

from typing import Any, Callable

from scheduler.bench_manager import BenchManager
from scheduler.resource_budget import ResourceBudgetManager
from scheduler.specialist_registry import SpecialistRegistry


ContextPackBuilder = Callable[[str, dict[str, Any], dict[str, Any], str, str], dict[str, Any]]


class OnDeckRuntime:
    """Deterministic scheduler for on-deck and warm-stage prefetch planning."""

    def __init__(
        self,
        *,
        specialist_registry: SpecialistRegistry,
        budget_manager: ResourceBudgetManager,
        bench_manager: BenchManager,
    ) -> None:
        self.specialist_registry = specialist_registry
        self.budget_manager = budget_manager
        self.bench_manager = bench_manager

    def plan_for_stage(
        self,
        *,
        stage: str,
        stage_state: dict[str, Any],
        payload: dict[str, Any],
        run_id: str,
        pipeline: str,
        spec_stages: list[str],
        current_context_pack: dict[str, Any],
        context_pack_builder: ContextPackBuilder,
        memory_state: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        stages = [str(x).strip() for x in spec_stages if str(x).strip()]
        if not stages or stage not in stages:
            return {"stage": stage, "pipeline": pipeline, "level1_prefetch": [], "level2_prefetch": [], "prefetched_context_packs": {}}

        domain = str(payload.get("topic_type", "") or current_context_pack.get("domain", "general_research")).strip() or "general_research"
        make_type = str(payload.get("target", "") or payload.get("make_type", "model_runtime_system")).strip() or "model_runtime_system"
        research_focus = str(payload.get("query_mode", "") or payload.get("research_focus", "implementation_focused")).strip() or "implementation_focused"

        idx = stages.index(stage)
        on_deck_depth, warm_depth = self.budget_manager.prefetch_depths()
        next_stages = stages[idx + 1 : idx + 1 + max(0, on_deck_depth)]
        warm_stages = stages[idx + 1 + max(0, on_deck_depth) : idx + 1 + max(0, on_deck_depth) + max(0, warm_depth)]

        current_manifest = self.specialist_registry.manifest_for_stage(
            stage=stage,
            pipeline=pipeline,
            next_stage=next_stages[0] if next_stages else "",
            domain=domain,
            make_type=make_type,
            research_focus=research_focus,
        ).as_dict()

        level1_prefetch: list[dict[str, Any]] = []
        level2_prefetch: list[dict[str, Any]] = []
        prefetched_context_packs: dict[str, dict[str, Any]] = {}

        for next_stage in next_stages:
            manifest = self.specialist_registry.manifest_for_stage(
                stage=next_stage,
                pipeline=pipeline,
                next_stage=self._next_after(stages, next_stage),
                domain=domain,
                make_type=make_type,
                research_focus=research_focus,
            ).as_dict()
            # Level 1 prefetch: full cognitive package
            stage_pack = context_pack_builder(next_stage, dict(stage_state), dict(payload), str(run_id), str(pipeline))
            if isinstance(stage_pack, dict):
                prefetched_context_packs[next_stage] = dict(stage_pack)
                manifest["prefetched_context_pack_id"] = str(stage_pack.get("context_pack_id", "")).strip()
                manifest["prefetched_token_budget"] = int(stage_pack.get("token_budget", 0) or 0)
            level1_prefetch.append(
                {
                    "stage": next_stage,
                    "specialist_role": manifest.get("specialist_role", ""),
                    "cognitive_package_ready": True,
                    "manifest": manifest,
                    "prefetch_level": "level1",
                }
            )

            adapter_required = bool(str(manifest.get("optional_adapter", "")).strip())
            if self.budget_manager.can_prefetch_neural(memory_state=memory_state, adapter_required=adapter_required):
                level2_prefetch.append(
                    {
                        "stage": next_stage,
                        "specialist_role": manifest.get("specialist_role", ""),
                        "adapter": manifest.get("optional_adapter", ""),
                        "prefetch_level": "level2",
                        "status": "scheduled",
                    }
                )

        warm_entries: list[dict[str, Any]] = []
        for warm_stage in warm_stages:
            manifest = self.specialist_registry.manifest_for_stage(
                stage=warm_stage,
                pipeline=pipeline,
                next_stage=self._next_after(stages, warm_stage),
                domain=domain,
                make_type=make_type,
                research_focus=research_focus,
            ).as_dict()
            warm_entries.append(
                {
                    "stage": warm_stage,
                    "specialist_role": manifest.get("specialist_role", ""),
                    "manifest": manifest,
                    "status": "partially_compiled",
                }
            )

        cold_entries: list[dict[str, Any]] = []
        consumed = {stage, *next_stages, *warm_stages}
        for pending in stages:
            if pending in consumed:
                continue
            manifest = self.specialist_registry.manifest_for_stage(
                stage=pending,
                pipeline=pipeline,
                next_stage=self._next_after(stages, pending),
                domain=domain,
                make_type=make_type,
                research_focus=research_focus,
            ).as_dict()
            cold_entries.append(
                {
                    "stage": pending,
                    "specialist_role": manifest.get("specialist_role", ""),
                    "status": "cold",
                }
            )

        bench_snapshot = self.bench_manager.build_snapshot(
            run_id=str(run_id),
            pipeline=str(pipeline),
            stage=str(stage),
            current_manifest=current_manifest,
            on_deck_entries=level1_prefetch,
            warm_entries=warm_entries,
            cold_entries=cold_entries,
        )

        return {
            "stage": stage,
            "pipeline": pipeline,
            "current_context_pack_id": str(current_context_pack.get("context_pack_id", "")).strip(),
            "cache_hierarchy": {
                "vram_hot_seat": current_manifest,
                "ram_on_deck": level1_prefetch,
                "ram_warm": warm_entries,
                "ssd_cold": cold_entries,
            },
            "level1_prefetch": level1_prefetch,
            "level2_prefetch": level2_prefetch,
            "prefetched_context_packs": prefetched_context_packs,
            "bench_snapshot": bench_snapshot,
        }

    @staticmethod
    def _next_after(stages: list[str], stage: str) -> str:
        if stage not in stages:
            return ""
        idx = stages.index(stage)
        if idx + 1 >= len(stages):
            return ""
        return stages[idx + 1]
