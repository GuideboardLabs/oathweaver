from __future__ import annotations

from datetime import datetime, timezone
from time import perf_counter
from typing import Any, Callable

from core.output_contracts import OutputContractAuditor, contract_for_stage
from core.state_store import StateStore
from core.model_runtime import ModelRuntime
from shared_tools.phase0 import lane_to_pipeline, normalize_domain

from .specs import PipelineSpec


StageRunner = Callable[[str, dict[str, Any], dict[str, Any]], dict[str, Any]]
ContextPackBuilder = Callable[[str, dict[str, Any], dict[str, Any], str, str], dict[str, Any]]
OnDeckPlanner = Callable[[str, dict[str, Any], dict[str, Any], str, str, dict[str, Any]], dict[str, Any]]


class PipelineEngine:
    """Deterministic stage sequencer with contract auditing and state logging."""

    def __init__(self, *, state_store: StateStore, auditor: OutputContractAuditor | None = None) -> None:
        self.state_store = state_store
        self.auditor = auditor or OutputContractAuditor()

    def execute(
        self,
        *,
        spec: PipelineSpec,
        input_payload: dict[str, Any],
        stage_runner: StageRunner,
        context_pack_builder: ContextPackBuilder | None = None,
        on_deck_planner: OnDeckPlanner | None = None,
        model_runtime: ModelRuntime | None = None,
    ) -> dict[str, Any]:
        payload = self._normalize_input_payload(spec, dict(input_payload or {}))
        self._validate_input_contract(spec, payload)
        started_at = datetime.now(timezone.utc).isoformat()

        run_id = self.state_store.start_run(
            project=str(payload.get("project_slug", "general")),
            pipeline=spec.name,
            input_contract={key: payload.get(key) for key in spec.input_contract},
        )

        stage_state: dict[str, Any] = {}
        outputs: dict[str, dict[str, Any]] = {}
        context_packs: dict[str, dict[str, Any]] = {}
        prefetched_context_cache: dict[str, dict[str, Any]] = {}
        on_deck_plans: dict[str, dict[str, Any]] = {}
        stage_audits: dict[str, dict[str, Any]] = {}
        stage_timings_ms: dict[str, int] = {}
        ok = True
        try:
            for stage in spec.stages:
                stage_t0 = perf_counter()
                context_pack: dict[str, Any] = {}
                cached = prefetched_context_cache.pop(stage, None)
                if isinstance(cached, dict) and cached:
                    context_pack = dict(cached)
                elif context_pack_builder is not None:
                    pack = context_pack_builder(stage, dict(stage_state), payload, run_id, spec.name)
                    if isinstance(pack, dict):
                        context_pack = dict(pack)
                on_deck_plan: dict[str, Any] = {}
                if on_deck_planner is not None:
                    model_memory_state: dict[str, Any] = {}
                    if model_runtime is not None:
                        try:
                            memory_row = model_runtime.get_memory_state()
                            if isinstance(memory_row, dict):
                                model_memory_state = dict(memory_row)
                        except Exception:
                            model_memory_state = {}
                    planner_payload = dict(payload)
                    if model_memory_state:
                        planner_payload["model_memory_state"] = dict(model_memory_state)
                    planned = on_deck_planner(
                        stage,
                        dict(stage_state),
                        planner_payload,
                        run_id,
                        spec.name,
                        {
                            "spec_stages": list(spec.stages),
                            "current_context_pack": dict(context_pack),
                            "prefetched_context_cache": dict(prefetched_context_cache),
                        },
                    )
                    if isinstance(planned, dict):
                        on_deck_plan = dict(planned)
                        prefetched = on_deck_plan.get("prefetched_context_packs", {})
                        if isinstance(prefetched, dict):
                            for key, value in prefetched.items():
                                if not isinstance(value, dict):
                                    continue
                                stage_key = str(key or "").strip()
                                if not stage_key:
                                    continue
                                prefetched_context_cache[stage_key] = dict(value)
                stage_payload = dict(payload)
                if context_pack:
                    stage_payload["context_pack"] = dict(context_pack)
                if on_deck_plan:
                    stage_payload["on_deck_plan"] = dict(on_deck_plan)
                output = stage_runner(stage, dict(stage_state), stage_payload)
                if not isinstance(output, dict):
                    raise RuntimeError(f"Stage '{stage}' returned non-dict output.")
                audit = self.auditor.validate(stage, output, contract_for_stage(stage))
                if not audit.ok:
                    ok = False
                outputs[stage] = dict(output)
                context_packs[stage] = dict(context_pack)
                on_deck_plans[stage] = dict(on_deck_plan)
                stage_audits[stage] = audit.as_dict()
                stage_timings_ms[stage] = int((perf_counter() - stage_t0) * 1000)
                stage_state[stage] = dict(output)
                self.state_store.write_stage_state(
                    run_id=run_id,
                    stage=stage,
                    state=dict(output),
                    contract_audit=audit.as_dict(),
                    context_pack=dict(context_pack),
                    on_deck_plan=dict(on_deck_plan),
                )
            final_state = outputs.get(spec.final_stage, {})
            self.state_store.finalize_run(run_id=run_id, ok=ok, final_state=dict(final_state))
            finished_at = datetime.now(timezone.utc).isoformat()
            return {
                "ok": ok,
                "run_id": run_id,
                "pipeline": spec.name,
                "stage_outputs": outputs,
                "context_packs": context_packs,
                "on_deck_plans": on_deck_plans,
                "stage_audits": stage_audits,
                "stage_timings_ms": stage_timings_ms,
                "final_stage": spec.final_stage,
                "final_output": dict(final_state),
                "started_at": started_at,
                "finished_at": finished_at,
            }
        except Exception as exc:
            self.state_store.finalize_run(
                run_id=run_id,
                ok=False,
                final_state={"error": str(exc)},
            )
            finished_at = datetime.now(timezone.utc).isoformat()
            return {
                "ok": False,
                "run_id": run_id,
                "pipeline": spec.name,
                "error": str(exc),
                "stage_outputs": outputs,
                "context_packs": context_packs,
                "on_deck_plans": on_deck_plans,
                "stage_audits": stage_audits,
                "stage_timings_ms": stage_timings_ms,
                "final_stage": spec.final_stage,
                "final_output": {},
                "started_at": started_at,
                "finished_at": finished_at,
            }

    @staticmethod
    def _validate_input_contract(spec: PipelineSpec, payload: dict[str, Any]) -> None:
        missing = [key for key in spec.input_contract if key not in payload]
        if missing:
            raise ValueError(f"Pipeline '{spec.name}' input contract missing keys: {', '.join(missing)}")

    @staticmethod
    def _normalize_input_payload(spec: PipelineSpec, payload: dict[str, Any]) -> dict[str, Any]:
        row = dict(payload)

        lane = str(row.get("lane", "")).strip()
        pipeline = str(row.get("pipeline", "")).strip()
        if not pipeline and lane:
            pipeline = lane_to_pipeline(lane)
            row["pipeline"] = pipeline
        if not lane and pipeline:
            low = pipeline.lower()
            if low == "research_pipeline":
                row["lane"] = "research"
            elif low in {"build_pipeline", "code_fix_pipeline"}:
                row["lane"] = "project"
            elif low == "conversation_pipeline":
                row["lane"] = "conversation"
            elif low.endswith("_pipeline"):
                row["lane"] = low[:-9]

        topic_type = str(row.get("topic_type", "")).strip()
        domain = str(row.get("domain", "")).strip()
        if not domain and topic_type:
            row["domain"] = normalize_domain(topic_type)
        if not topic_type and domain:
            row["topic_type"] = domain

        # Keep transition aliases for internal callers that still reference legacy keys.
        if spec.name.endswith("_pipeline"):
            row.setdefault("pipeline", spec.name)
        return row
