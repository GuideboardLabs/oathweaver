from __future__ import annotations

import json
import mimetypes
import os
import sys
import re
import threading
import time
import uuid
from copy import deepcopy
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
SOURCE = ROOT / "SourceCode"
if str(SOURCE) not in sys.path:
    sys.path.insert(0, str(SOURCE))

from shared_tools.activity_bus import ActivityBus
from shared_tools.activity_store import ActivityStore
from shared_tools.approval_gate import ApprovalGate
from shared_tools.context_policy import analyze_query_context, build_context_usage_guidance, evaluate_context_use
from shared_tools.domain_reputation import DomainReputation
from shared_tools.feedback_learning import ORIGIN_REFLECTION
from shared_tools.handoff_queue import HandoffQueue
from shared_tools.hardware_profiles import (
    hardware_profile_summary,
    hardware_profile_to_scheduler,
    resolve_active_hardware_profile,
)
from shared_tools.model_routing import load_model_routing, lane_model_config
from shared_tools.inference_router import InferenceRouter
from shared_tools.web_research import build_web_progress_payload
from shared_tools.answer_composer import compose_research_summary, evaluate_answer_confidence
from shared_tools.document_ingestion import is_document_ext
from shared_tools.fact_cards import render_fact_card_markdown
from shared_tools.fact_policy import classify_fact_volatility, detect_topic_type
from shared_tools.perf_trace import PerfTrace
from shared_tools.phase0 import lane_to_pipeline, serious_mode_enabled
from cag.contradiction_detector import ContradictionDetector
from cag.decision_ledger import DecisionLedger
from cag.memory_store import CAGMemoryStore
from cag.promotion_gate import PromotionGate
from cag.selector import ScopedSelector
from auditor import AuditorEngine, BenchmarkImport, RegressionReporter
from core.context_compiler import ContextCompiler
from core.context_pack import ContextPackStore
from core.capability_registry import CapabilityRegistry
from core.model_runtime import build_model_runtime
from core.output_contracts import OutputContractAuditor, contract_for_stage
from core.pipeline_engine import PipelineEngine, pipeline_spec_for_name
from core.replay import ReplayStore
from core.state_store import StateStore
from core.trace_ledger import TraceLedger
from core.project_kernel import ProjectKernelStore
from benchmarks.paths import default_cag_bench_results_root
from scheduler import BenchManager, OnDeckRuntime, ResourceBudgetManager, SpecialistRegistry
from orchestrator.pipelines import (
    get_turn_trace,
    invoke_chat_turn_graph,
    list_turns,
    replay_turn,
    run_regression_suite,
)
from orchestrator.services import OrchestratorInfraRuntime, ResearchService, TurnPlanner, WorkerResult
from orchestrator.services.agent_contracts import AgentTask
from orchestrator.services.agent_registry import build_default_agent_registry
from orchestrator.services.self_query_gate import SelfQueryGate
from orchestrator.services.self_state import SelfStateService
from orchestrator.services import cag_helpers as _cag_helpers
from orchestrator.services.policy import _resolve_domain, should_route_web_fetch
from orchestrator.text_processing.text_analysis import (
    RECENCY_TERMS,
    is_recency_sensitive,
    is_recency_sensitive_from_history,
    is_evolving_topic,
    extract_rejected_tool,
    should_offer_web,
)
from orchestrator.text_processing.request_filters import is_reminder_only_request, is_event_only_request
from orchestrator.text_processing.delivery_classifier import infer_delivery_target
from orchestrator.oathweaver.identity import (
    OATHWEAVER_ALIASES,
    OATHWEAVER_ADDRESS_NEXT_WORDS,
    OATHWEAVER_IDENTITY_CUES,
    mentions_oathweaver_alias,
    strip_oathweaver_vocative_prefix as _strip_vocative_prefix,
    is_oathweaver_self_query as _is_gb_self_query,
)
from orchestrator.oathweaver.manifesto import (
    load_manifesto_text as _load_manifesto,
    manifesto_principles_block as _manifesto_principles,
    weaver_persona_block as _weaver_persona_block,
    overseer_persona_block as _gb_persona_block,
    oathweaver_identity_reply as _gb_identity_reply,
)
from orchestrator.learning import lesson_manager as _lesson_mgr
from orchestrator.actions import handoff_manager as _handoff_mgr
from orchestrator.status import build_status_text as _build_status_text
from orchestrator.memory.reminder_parser import extract_reminder_from_text as _extract_reminder
from orchestrator.memory.research_memory import (
    latest_research_summary_preview as _latest_research_preview,
    read_research_context as _read_research_ctx,
    read_raw_notes_context as _read_raw_notes_ctx,
    read_sources_context as _read_sources_ctx,
)

# Short social/acknowledgment tokens that don't need heavy context injection.
_SOCIAL_PATTERNS = frozenset({
    "ok", "okay", "cool", "nice", "great", "thanks", "thank you", "thx",
    "no problem", "no worries", "np", "got it", "gotcha", "sounds good",
    "perfect", "awesome", "sweet", "good", "lol", "lmao", "haha", "ha", "heh",
    "yep", "yup", "yeah", "yes", "nah", "nope", "sure", "right",
    "makes sense", "fair enough", "true", "agreed", "exactly",
    "my bad", "sorry", "all good", "you too", "same", "word",
    "bet", "for sure", "absolutely", "definitely", "of course",
    "no doubt", "understood", "will do", "on it",
})

_CASUAL_CONVERSATION_PHRASES = frozenset({
    "what do you think",
    "do you think",
    "be honest",
    "tell me straight",
    "how are you",
    "how's it going",
    "hows it going",
    "you there",
    "you good",
    "fair enough",
    "makes sense",
    "i agree",
    "i disagree",
    "that's funny",
    "that is funny",
    "that's wild",
    "that is wild",
    "that's crazy",
    "that is crazy",
})

_BUILD_INTENT_TERMS = frozenset({
    "build", "create", "make", "generate", "draft", "design", "redesign",
    "implement", "code", "develop", "scaffold", "spec", "prototype",
    "produce", "assemble", "ship", "write the", "launch",
})

_LIVE_VERIFICATION_MARKERS = frozenset({
    "today", "tonight", "right now", "live", "latest", "current", "recent",
    "upcoming", "next", "this weekend", "this week", "breaking",
    "odds", "line", "spread", "moneyline", "favorite",
    "score", "result", "winner", "standings", "ranking", "bracket", "playoff",
    "fight card", "main card", "prelims", "co-main", "main event", "weigh-in",
    "kickoff", "tipoff", "broadcast", "stream", "airing", "start time",
    "who is on", "who's on", "when is", "what time", "scheduled",
})

_SURFACE_POLISH_SKIP_TOKENS = (
    "```",
    "[FORAGE:",
    "[ADD_TASK:",
    "[ADD_EVENT:",
    "[ADD_SHOPPING:",
    "[ADD_ROUTINE:",
)
def _has_build_intent(text: str) -> bool:
    low = text.lower()
    for term in _BUILD_INTENT_TERMS:
        if " " in term or "-" in term:
            if term in low:
                return True
        elif re.search(rf"\b{re.escape(term)}\b", low):
            return True
    return False


def _make_lane_for_target(target: str) -> str:
    from orchestrator.services.make_catalog import lane_for_type
    return lane_for_type(target)


def _ingest_canon_seed_files(repo_root: Path, store: CAGMemoryStore) -> None:
    """Idempotently ingest all canon seed JSON files into CAG memory."""
    seeds_dir = repo_root / "SourceCode" / "agents_make" / "canon" / "seeds"
    if not seeds_dir.exists():
        return

    existing = store.list_rows(project="general", include_expired=True, include_superseded=True, limit=4000)
    existing_tags: set[str] = set()
    for row in existing:
        for tag in row.get("tags", []) if isinstance(row.get("tags", []), list) else []:
            token = str(tag).strip().lower()
            if token:
                existing_tags.add(token)

    for seed_path in sorted(seeds_dir.glob("*.json")):
        seed_key = f"canon_seed_{seed_path.stem}".lower()
        if seed_key in existing_tags:
            continue
        try:
            payload = json.loads(seed_path.read_text(encoding="utf-8"))
        except Exception:
            continue
        if not isinstance(payload, dict):
            continue

        scope = payload.get("scope", {}) if isinstance(payload.get("scope", {}), dict) else {}
        domain = str(scope.get("domain", "computer_science_programming")).strip() or "computer_science_programming"
        topic = str(scope.get("topic", "web_app")).strip() or "web_app"
        make_type = str(scope.get("make_type", "web_app")).strip() or "web_app"
        content = str(payload.get("content", "")).strip()
        if not content:
            continue

        tags = [str(x).strip().lower() for x in payload.get("tags", []) if str(x).strip()]
        if seed_key not in tags:
            tags.append(seed_key)
        if make_type and make_type not in tags:
            tags.append(make_type)

        store.add_row(
            {
                "text": content,
                "scope": f"domain:{domain}",
                "scope_level": "domain",
                "domain": domain,
                "topic": topic,
                "thread": "thread_general",
                "project": "general",
                "run": f"seed_{seed_path.stem}",
                "type": "constraint",
                "status": "accepted",
                "human_status": "accepted",
                "evidence": [{"kind": "seed_file", "value": str(seed_path)}],
                "confidence": 0.98,
                "tags": tags,
                "promoted_terms": ["flask", "vue", "sqlite", "login", "crud"],
                "source": f"canon_seed:{seed_path.stem}",
                "validation": {
                    "task_metadata": True,
                    "has_citation": True,
                    "auditor_approved": True,
                    "user_accepted": True,
                },
            }
        )
        existing_tags.add(seed_key)


class OathweaverOrchestrator:
    def __init__(self, repo_root: Path) -> None:
        self.repo_root = repo_root
        self.turn_planner = TurnPlanner(repo_root)
        self.bus = ActivityBus(repo_root)
        self.activity_store = ActivityStore(repo_root)
        self.approval_gate = ApprovalGate(repo_root)
        self.handoff_queue = HandoffQueue(repo_root)
        self.ollama = InferenceRouter(repo_root)
        self._infra = OrchestratorInfraRuntime(repo_root, self.ollama)
        self.research_service = ResearchService(repo_root)
        self.agent_registry = build_default_agent_registry()
        self.project_slug = "general"
        self.project_kernel_store = ProjectKernelStore(repo_root)
        self.project_kernel_store.get_or_create(self.project_slug)
        self.state_store = StateStore(repo_root)
        self.output_contract_auditor = OutputContractAuditor()
        self.pipeline_engine = PipelineEngine(
            state_store=self.state_store,
            auditor=self.output_contract_auditor,
        )
        self.model_runtime = build_model_runtime(repo_root)
        self.context_pack_store = ContextPackStore(repo_root)
        self.context_compiler = ContextCompiler(context_pack_store=self.context_pack_store)
        self.hardware_profile = resolve_active_hardware_profile(repo_root)
        self.resource_budget_manager = ResourceBudgetManager(
            profile=hardware_profile_to_scheduler(self.hardware_profile)
        )
        self.specialist_registry = SpecialistRegistry()
        self.bench_manager = BenchManager(repo_root)
        self.on_deck_runtime = OnDeckRuntime(
            specialist_registry=self.specialist_registry,
            budget_manager=self.resource_budget_manager,
            bench_manager=self.bench_manager,
        )
        self.trace_ledger = TraceLedger(repo_root)
        self.replay_store = ReplayStore(repo_root)
        self.capability_registry = CapabilityRegistry(repo_root)
        self.self_query_gate = SelfQueryGate(embed_client=self.ollama, threshold=0.75, repo_root=repo_root)
        self.self_state_service = SelfStateService(
            router=self.ollama,
            capability_registry=self.capability_registry,
            cag_store=self.cag_memory_store if hasattr(self, "cag_memory_store") else None,
            hardware_profile_provider=lambda: self.hardware_profile,
            project_slug_provider=lambda: self.project_slug,
        )
        self.benchmark_import = BenchmarkImport(default_cag_bench_results_root(self.repo_root))
        self.auditor_engine = AuditorEngine(benchmark_import=self.benchmark_import)
        self.regression_reporter = RegressionReporter(repo_root)
        self.cag_memory_store = CAGMemoryStore(repo_root)
        self.self_state_service.cag_store = self.cag_memory_store
        _ingest_canon_seed_files(repo_root, self.cag_memory_store)
        self.cag_selector = ScopedSelector()
        self.cag_promotion_gate = PromotionGate()
        self.cag_contradiction_detector = ContradictionDetector()
        self.cag_decision_ledger = DecisionLedger(repo_root)
        self.model_routing = load_model_routing(repo_root)
        # Build the tool registry lazily. Eager construction pulls in several
        # DB-backed stores for every lightweight panel/status request and can
        # contend on SQLite locks under load.
        self._tool_registry = None
        self.manifesto_path = self.repo_root / "Runtime" / "config" / "oathweaver_manifesto.md"
        self._manifesto_cache_mtime: float = -1.0
        self._manifesto_cache_text: str = ""
        self._project_research_brief_cache: dict[tuple[str, float, int], dict[str, Any]] = {}
        self._project_make_brief_cache: dict[tuple[str, float, int, int], str] = {}
        self._warmup_models_async()


    @property
    def web_engine(self):
        return self._infra.web_engine

    @property
    def external_tools_settings(self):
        return self._infra.external_tools_settings

    @property
    def external_request_store(self):
        return self._infra.external_request_store

    @property
    def project_memory(self):
        return self._infra.project_memory

    @property
    def topic_memory(self):
        return self._infra.topic_memory

    @property
    def pipeline_store(self):
        return self._infra.pipeline_store

    @property
    def learning_engine(self):
        return self._infra.learning_engine

    @property
    def improvement_engine(self):
        return self._infra.improvement_engine

    @property
    def reflection_engine(self):
        return self._infra.reflection_engine

    @property
    def workspace_tools(self):
        return self._infra.workspace_tools

    @property
    def embedding_memory(self):
        return self._infra.embedding_memory

    @property
    def library_service(self):
        return self._infra.library_service

    @property
    def watchtower(self):
        return self._infra.watchtower

    @property
    def tool_registry(self):
        if self._tool_registry is None:
            self._tool_registry = self._infra.build_tool_registry(bus=self.bus)
        return self._tool_registry

    def _warmup_models_async(self) -> None:
        if str(os.getenv("OATHWEAVERX_ENABLE_MODEL_WARMUP", "0")).strip().lower() not in {"1", "true", "yes", "on"}:
            return
        try:
            model_names = self._routing_model_names(limit=12)
        except Exception:
            model_names = []
        if not model_names:
            return

        def _worker() -> None:
            try:
                self.ollama.warmup_models(model_names)
            except Exception:
                return

        threading.Thread(
            target=_worker,
            daemon=True,
            name=f"oathweaver-model-warmup-{uuid.uuid4().hex[:8]}",
        ).start()

    def _routing_model_names(self, *, limit: int = 12) -> list[str]:
        names: list[str] = []
        routing = self.model_routing if isinstance(self.model_routing, dict) else {}
        for cfg in routing.values():
            if not isinstance(cfg, dict):
                continue
            for key in ("model",):
                name = str(cfg.get(key, "")).strip()
                if name and name not in names:
                    names.append(name)
            for tier_key in ("tier_default", "tier_premium"):
                tier_cfg = cfg.get(tier_key)
                if not isinstance(tier_cfg, dict):
                    continue
                model = str(tier_cfg.get("model", "")).strip()
                if model and model not in names:
                    names.append(model)
            fallbacks = cfg.get("fallback_models", [])
            if isinstance(fallbacks, list):
                for model in fallbacks:
                    name = str(model or "").strip()
                    if name and name not in names:
                        names.append(name)
            if len(names) >= max(1, int(limit)):
                break
        return names[: max(1, int(limit))]

    def _make_agent_task(
        self,
        *,
        lane: str,
        text: str,
        history: list[dict[str, str]] | None = None,
        context: dict[str, Any] | None = None,
        cancel_checker=None,
        pause_checker=None,
        yield_checker=None,
        progress_callback=None,
    ) -> AgentTask:
        return AgentTask(
            lane=lane,
            prompt=text,
            project_slug=self.project_slug,
            repo_root=self.repo_root,
            history=list(history or []),
            context=dict(context or {}),
            cancel_checker=cancel_checker,
            pause_checker=pause_checker,
            yield_checker=yield_checker,
            progress_callback=progress_callback,
        )

    def _run_registered_agent(self, lane: str, task: AgentTask) -> dict[str, Any]:
        agent = self.agent_registry.require(lane)
        result = agent.run(task, self.tool_registry)
        if hasattr(result, "payload") and isinstance(result.payload, dict) and result.payload:
            return dict(result.payload)
        return result.as_dict()

    @staticmethod
    def _resolved_pipeline_domain(turn_plan: Any) -> str:
        return _cag_helpers.resolved_pipeline_domain(
            str(getattr(turn_plan, "make_type", "") or ""),
            str(getattr(turn_plan, "domain", "") or ""),
            _resolve_domain,
        )

    @staticmethod
    def _select_context_memory_rows(
        selector: ScopedSelector,
        *,
        payload: dict[str, Any],
        project_rows: list[dict[str, Any]],
        domain_rows: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        return _cag_helpers.select_context_memory_rows(
            selector,
            payload=payload,
            project_rows=project_rows,
            domain_rows=domain_rows,
        )

    def _scoped_rows_with_scores(
        self,
        *,
        text: str,
        tags: list[str],
        continuity_terms: list[str],
        projects: list[str],
        limit: int = 500,
        k: int = 40,
    ) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]]:
        candidate_rows = self.cag_memory_store.list_rows_for_projects(
            projects=projects,
            include_expired=True,
            include_superseded=True,
            limit=limit,
        )
        candidate_rows = self._sort_memory_rows_oldest_first(candidate_rows)
        scoped_rows, selector_scores = self.cag_selector.retrieve_scoped(
            task={
                "title": str(text or ""),
                "prompt": str(text or ""),
                "tags": list(tags or []),
                "continuity_terms": list(continuity_terms or []),
            },
            rows=candidate_rows,
            k=max(1, int(k)),
            return_scores=True,
        )
        return candidate_rows, scoped_rows, selector_scores

    @staticmethod
    def _parse_json_object(raw: str) -> dict[str, Any]:
        text = str(raw or "").strip()
        if not text:
            return {}
        try:
            parsed = json.loads(text)
            if isinstance(parsed, dict):
                return parsed
        except Exception:
            pass
        match = re.search(r"\{[\s\S]*\}", text)
        if not match:
            return {}
        try:
            parsed = json.loads(match.group(0))
            return parsed if isinstance(parsed, dict) else {}
        except Exception:
            return {}

    def _stage_llm_json_call(
        self,
        *,
        label: str,
        system_prompt: str,
        user_prompt: str,
        lane_key: str = "orchestrator_reasoning",
    ) -> tuple[dict[str, Any], dict[str, Any]]:
        cfg = lane_model_config(self.repo_root, str(lane_key or "orchestrator_reasoning").strip())
        if not cfg:
            cfg = lane_model_config(self.repo_root, "orchestrator_reasoning")
        model = str(cfg.get("model", "")).strip()
        started = time.monotonic()
        if not model:
            detail = {"label": label, "ok": False, "error": "no_model_configured", "latency_ms": 0}
            self.bus.emit("orchestrator", "stage_llm_no_model", {"label": label})
            return {}, detail
        try:
            raw = self.ollama.chat(
                model=model,
                system_prompt=system_prompt,
                user_prompt=user_prompt,
                prior_messages=[],
                temperature=float(cfg.get("temperature", 0.1)),
                num_ctx=int(cfg.get("num_ctx", 12288)),
                think=bool(cfg.get("think", False)),
                timeout=int(cfg.get("timeout_sec", 120) or 120),
                retry_attempts=int(cfg.get("retry_attempts", 2)),
                retry_backoff_sec=float(cfg.get("retry_backoff_sec", 1.0)),
                fallback_models=cfg.get("fallback_models", []) if isinstance(cfg.get("fallback_models", []), list) else [],
            )
            latency_ms = int((time.monotonic() - started) * 1000)
            parsed = self._parse_json_object(str(raw or ""))
            detail = {
                "label": label,
                "ok": bool(parsed),
                "latency_ms": latency_ms,
                "response_tokens": max(0, len(str(raw or "").split())),
            }
            if not parsed:
                detail["error"] = "empty_or_unparseable_json"
            return parsed, detail
        except Exception as exc:
            detail = {
                "label": label,
                "ok": False,
                "error": str(exc)[:220],
                "latency_ms": int((time.monotonic() - started) * 1000),
            }
            self.bus.emit("orchestrator", "build_stage_llm_failed", {"label": label, "error": str(exc)[:220]})
            return {}, detail

    def _llm_extract_requirements(
        self,
        *,
        text: str,
        topic_type: str,
        target: str,
        lane: str,
        lane_key: str = "orchestrator_reasoning",
    ) -> dict[str, Any]:
        system_prompt = (
            "Extract concrete build requirements. Return JSON only with keys: "
            "entities (list[str]), actions (list[str]), constraints (list[str]). "
            "Keep each item short and concrete."
        )
        user_prompt = (
            f"Request:\n{text.strip()}\n\n"
            f"Topic type: {topic_type}\nTarget: {target}\nLane: {lane}\n"
        )
        parsed, call_meta = self._stage_llm_json_call(
            label="requirements",
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            lane_key=lane_key,
        )
        entities = [str(x).strip() for x in parsed.get("entities", []) if str(x).strip()] if isinstance(parsed.get("entities", []), list) else []
        actions = [str(x).strip() for x in parsed.get("actions", []) if str(x).strip()] if isinstance(parsed.get("actions", []), list) else []
        constraints = [str(x).strip() for x in parsed.get("constraints", []) if str(x).strip()] if isinstance(parsed.get("constraints", []), list) else []
        return {
            "entities": entities[:20],
            "actions": actions[:30],
            "constraints": constraints[:30],
            "llm_sub_calls": [call_meta],
        }

    def _llm_propose_architecture(
        self,
        *,
        request: str,
        make_type: str,
        requirements: dict[str, Any],
        lane_key: str = "orchestrator_reasoning",
    ) -> dict[str, Any]:
        system_prompt = (
            "Propose a concise architecture outline. Return JSON only with keys: "
            "stack_summary (str), modules (list[object with name and responsibility])."
        )
        user_prompt = (
            f"Request:\n{request.strip()}\n\n"
            f"Make type: {make_type}\n"
            f"Requirements JSON:\n{json.dumps(requirements, ensure_ascii=True)[:3000]}"
        )
        parsed, call_meta = self._stage_llm_json_call(
            label="architecture",
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            lane_key=lane_key,
        )
        modules_raw = parsed.get("modules", [])
        modules: list[dict[str, str]] = []
        if isinstance(modules_raw, list):
            for item in modules_raw[:20]:
                if not isinstance(item, dict):
                    continue
                name = str(item.get("name", "")).strip()
                responsibility = str(item.get("responsibility", "")).strip()
                if name:
                    modules.append({"name": name, "responsibility": responsibility})
        stack_summary = str(parsed.get("stack_summary", "")).strip()
        return {"stack_summary": stack_summary, "modules": modules, "llm_sub_calls": [call_meta]}

    def _llm_propose_implementation_plan(
        self,
        *,
        request: str,
        architecture: dict[str, Any],
        lane_key: str = "orchestrator_reasoning",
    ) -> dict[str, Any]:
        system_prompt = (
            "Create an ordered implementation plan. Return JSON only with keys: "
            "steps (list[str]), files (list[str])."
        )
        user_prompt = (
            f"Request:\n{request.strip()}\n\n"
            f"Architecture JSON:\n{json.dumps(architecture, ensure_ascii=True)[:3500]}"
        )
        parsed, call_meta = self._stage_llm_json_call(
            label="implementation_plan",
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            lane_key=lane_key,
        )
        steps = [str(x).strip() for x in parsed.get("steps", []) if str(x).strip()] if isinstance(parsed.get("steps", []), list) else []
        files = [str(x).strip() for x in parsed.get("files", []) if str(x).strip()] if isinstance(parsed.get("files", []), list) else []
        return {"steps": steps[:40], "files": files[:40], "llm_sub_calls": [call_meta]}

    def _select_pipeline_for_lane(self, lane: str, query_mode: str = "") -> str:
        lane_key = str(lane or "").strip().lower()
        if lane_key in {"research", "project"}:
            return "research_pipeline"
        if lane_key in {"make_app", "make_doc", "make_plan", "make_tool", "make_creative", "make_content", "make_specialist", "make_longform", "make_desktop_app", "ui"}:
            if str(query_mode or "").strip().lower() == "workspace_code":
                return "code_fix_pipeline"
            return "build_pipeline"
        return ""

    def _execute_pipeline_turn(
        self,
        *,
        lane: str,
        text: str,
        history: list[dict[str, str]] | None,
        topic_type: str,
        query_mode: str,
        query_complexity: str,
        inferred_target: str,
        mode: str,
        turn_plan: Any,
        force_research: bool,
        cancel_checker=None,
        pause_checker=None,
        yield_checker=None,
        progress_callback=None,
        reminder_note: str = "",
        event_note: str = "",
        details_sink: dict[str, Any] | None = None,
        household_context: str = "",
        resolved_domain: str = "general_research",
    ) -> str | None:
        lane_key = str(lane or "").strip().lower()
        if lane_key in {"conversation", "personal"}:
            return None

        pipeline_name = self._select_pipeline_for_lane(lane_key, query_mode=query_mode)
        if not pipeline_name:
            return None
        spec = pipeline_spec_for_name(pipeline_name)
        if spec is None:
            return None

        default_stage_budget = int(self.resource_budget_manager.stage_context_budget())
        adaptive_hint = int(self.bench_manager.recommended_stage_budget(default_budget=default_stage_budget))
        adaptive_stage_budget = int(self.resource_budget_manager.stage_context_budget(requested_tokens=adaptive_hint))
        pipeline_context: dict[str, Any] = {
            "text": text,
            "project_slug": self.project_slug,
            "domain": str(resolved_domain or "general_research").strip().lower() or "general_research",
            "pipeline": pipeline_name,
            "topic_type": topic_type,
            "lane": lane_key,
            "target": inferred_target,
            "query_mode": query_mode,
            "query_complexity": query_complexity,
            "mode": mode,
            "history": list(history or []),
            "hardware_token_budget": adaptive_stage_budget,
            "hardware_profile": hardware_profile_summary(self.hardware_profile),
        }
        scratch: dict[str, Any] = {
            "web_note": "",
            "web_context": "",
            "web_details": {},
            "worker_result": {},
            "reply": "",
        }

        def _stage_runner(stage: str, stage_state: dict[str, Any], payload: dict[str, Any]) -> dict[str, Any]:
            if pipeline_name == "research_pipeline":
                if stage == "intake":
                    return {
                        "question": payload["text"],
                        "project": payload["project_slug"],
                        "topic_type": payload["topic_type"],
                        "lane": payload["lane"],
                    }
                if stage == "domain_framing":
                    kernel = self.project_kernel_store.snapshot(self.project_slug)
                    knowledge = kernel.get("knowledge_spine", {}) if isinstance(kernel.get("knowledge_spine", {}), dict) else {}
                    return {
                        "domain": str(knowledge.get("domain", "general_research")).strip(),
                        "topic": str(knowledge.get("topic", payload.get("topic_type", "general"))).strip(),
                        "thread": str(knowledge.get("thread", f"thread_{self.project_slug}")).strip(),
                    }
                if stage == "source_discovery":
                    web_note, web_context, web_details = self._prepare_web_context(
                        text=payload["text"],
                        lane="research" if payload["lane"] == "research" else "project",
                        topic_type=payload["topic_type"],
                        force=True,
                        progress_callback=progress_callback,
                    )
                    scratch["web_note"] = web_note
                    scratch["web_context"] = web_context
                    scratch["web_details"] = dict(web_details or {})
                    return {
                        "web_context": web_context,
                        "web_note": web_note,
                        "source_count": int((web_details or {}).get("source_count", 0) or 0),
                    }
                if stage == "evidence_analysis":
                    web_details = scratch.get("web_details", {}) if isinstance(scratch.get("web_details", {}), dict) else {}
                    source_count = int(web_details.get("source_count", 0) or 0)
                    stack = web_details.get("web_stack", {}) if isinstance(web_details.get("web_stack", {}), dict) else {}
                    return {
                        "evidence_summary": (
                            f"Captured {source_count} source(s) using web mode "
                            f"{str(stack.get('mode', 'auto')).strip() or 'auto'}."
                        ),
                    }
                if stage == "nuance_pass":
                    source_count = int((stage_state.get("source_discovery", {}) or {}).get("source_count", 0) or 0)
                    open_risks = []
                    if source_count <= 0:
                        open_risks.append("No live sources were captured.")
                    if str(payload.get("query_complexity", "")).strip().lower() == "deep":
                        open_risks.append("Deep query path may need follow-up validation passes.")
                    return {"open_risks": open_risks}
                if stage == "synthesis":
                    if payload["lane"] == "research":
                        reply = self.research_service.execute_research_lane(
                            self,
                            text=payload["text"],
                            history=payload["history"],
                            topic_type=payload["topic_type"],
                            turn_plan=turn_plan,
                            force_research=force_research,
                            cancel_checker=cancel_checker,
                            pause_checker=pause_checker,
                            yield_checker=yield_checker,
                            progress_callback=progress_callback,
                            perf=None,
                            reminder_note=reminder_note,
                            event_note=event_note,
                            lane="research",
                            details_sink=details_sink,
                        )
                    else:
                        reply = self.research_service.execute_project_lane(
                            self,
                            text=payload["text"],
                            history=payload["history"],
                            topic_type=payload["topic_type"],
                            cancel_checker=cancel_checker,
                            pause_checker=pause_checker,
                            yield_checker=yield_checker,
                            progress_callback=progress_callback,
                            reminder_note=reminder_note,
                            event_note=event_note,
                            details_sink=details_sink,
                        )
                    scratch["reply"] = str(reply or "")
                    return {"reply": str(reply or "")}
                if stage == "cag_promotion_gate":
                    kernel = self.project_kernel_store.snapshot(self.project_slug)
                    scope_row = kernel.get("current_scope", {}) if isinstance(kernel.get("current_scope", {}), dict) else {}
                    candidate = self._build_cag_candidate(
                        text=str(scratch.get("reply", "")),
                        payload=payload,
                        scope_row=scope_row,
                        web_details=scratch.get("web_details", {}),
                    )
                    if not candidate:
                        return {
                            "promotion_candidates": [],
                            "accepted_memory_ids": [],
                            "rejected_reasons": ["empty_candidate"],
                            "contradictions": [],
                            "contradiction_budget": {"non_error_budget": 0, "non_error_count": 0, "exceeded": False},
                            "selector_scores": [],
                            "decision_ledger_entries": [],
                        }

                    _rows, scoped_rows, selector_scores = self._scoped_rows_with_scores(
                        text=str(payload.get("text", "")),
                        tags=list(candidate.get("tags", [])),
                        continuity_terms=list(candidate.get("promoted_terms", [])),
                        projects=[self.project_slug, "general"],
                        limit=500,
                        k=40,
                    )
                    contradictions = self.cag_contradiction_detector.detect(candidate=candidate, existing_rows=scoped_rows)
                    contradiction_budget = self.cag_contradiction_detector.contradiction_budget(
                        contradictions=contradictions,
                        non_error_budget=int(os.getenv("OATHWEAVERX_CONTRADICTION_BUDGET", "6")),
                    )
                    gate = self.cag_promotion_gate.evaluate(
                        candidate={**candidate, "contradictions": contradictions},
                        existing_rows=scoped_rows,
                        contradictions=contradictions,
                        contradiction_budget=contradiction_budget,
                    )
                    decision = gate.as_dict()
                    normalized = decision.get("normalized_candidate", {})
                    promotion_candidates = []
                    accepted_memory_ids: list[str] = []
                    rejected_reasons = list(decision.get("reasons", []))
                    ledger_entries: list[dict[str, Any]] = []

                    if normalized:
                        promotion_candidates.append(
                            {
                                "type": str(normalized.get("type", "")),
                                "scope": str(normalized.get("scope", "")),
                                "human_status": str(normalized.get("human_status", "unreviewed")),
                                "status": str(normalized.get("status", "candidate")),
                                "confidence": float(normalized.get("confidence", 0.0) or 0.0),
                            }
                        )
                    if decision.get("accepted", False):
                        persisted = self.cag_memory_store.add_row(normalized)
                        accepted_memory_ids.append(str(persisted.get("memory_id", "")).strip())
                        supersedes = list(persisted.get("supersedes", []))
                        for memory_id in supersedes:
                            if str(memory_id).strip():
                                self.cag_memory_store.mark_supersession(
                                    old_memory_id=str(memory_id),
                                    new_memory_id=str(persisted.get("memory_id", "")),
                                )
                        ledger = self.cag_decision_ledger.add_entry(
                            memory_row=persisted,
                            rationale="Promoted through cag_promotion_gate.",
                            status="accepted",
                        )
                        if isinstance(ledger, dict):
                            ledger_entries.append(dict(ledger))

                    return {
                        "promotion_candidates": promotion_candidates,
                        "accepted_memory_ids": accepted_memory_ids,
                        "rejected_reasons": rejected_reasons,
                        "contradictions": contradictions,
                        "contradiction_budget": contradiction_budget,
                        "selector_scores": selector_scores,
                        "decision_ledger_entries": ledger_entries,
                    }

            if pipeline_name == "build_pipeline":
                plan_lane_key = "make_plan" if str(payload.get("lane", "")).strip().lower() == "make_plan" else "orchestrator_reasoning"
                if stage == "requirements":
                    extracted = self._llm_extract_requirements(
                        text=payload["text"],
                        topic_type=str(payload.get("topic_type", "general")),
                        target=str(payload.get("target", "")),
                        lane=str(payload.get("lane", "")),
                        lane_key=plan_lane_key,
                    )
                    return {
                        "requirements": {
                            "request": payload["text"],
                            "target": payload["target"],
                            "lane": payload["lane"],
                            "extracted_entities": list(extracted.get("entities", [])),
                            "extracted_actions": list(extracted.get("actions", [])),
                            "extracted_constraints": list(extracted.get("constraints", [])),
                        },
                        "llm_sub_calls": list(extracted.get("llm_sub_calls", [])),
                    }
                if stage == "architecture":
                    kernel = self.project_kernel_store.snapshot(self.project_slug)
                    execution = kernel.get("execution_spine", {}) if isinstance(kernel.get("execution_spine", {}), dict) else {}
                    architecture = self._llm_propose_architecture(
                        request=payload["text"],
                        make_type=str(execution.get("make_type", payload.get("target", "web_app"))),
                        requirements=stage_state.get("requirements", {}),
                        lane_key=plan_lane_key,
                    )
                    return {
                        "architecture_outline": {
                            "pipeline": str(execution.get("pipeline", "build_pipeline")).strip(),
                            "make_type": str(execution.get("make_type", "research_brief")).strip(),
                            "research_focus": str(execution.get("research_focus", "implementation_focused")).strip(),
                            "module_breakdown": list(architecture.get("modules", [])),
                            "stack_summary": str(architecture.get("stack_summary", "")).strip(),
                        },
                        "llm_sub_calls": list(architecture.get("llm_sub_calls", [])),
                    }
                if stage == "implementation_plan":
                    implementation = self._llm_propose_implementation_plan(
                        request=payload["text"],
                        architecture=stage_state.get("architecture_outline", {}),
                        lane_key=plan_lane_key,
                    )
                    return {
                        "implementation_plan": {
                            "route_lane": payload["lane"],
                            "target": payload["target"],
                            "mode": payload["mode"],
                            "ordered_steps": list(implementation.get("steps", [])),
                            "deliverable_files": list(implementation.get("files", [])),
                        },
                        "llm_sub_calls": list(implementation.get("llm_sub_calls", [])),
                    }
                if stage == "patch_artifact_generation":
                    self._last_project_mode = self.pipeline_store.get(self.project_slug)
                    self._last_progress_callback = progress_callback
                    self._last_cancel_checker = cancel_checker
                    if str(payload.get("lane", "")).strip().lower() == "make_plan":
                        out = self._run_make_plan(
                            text=payload["text"],
                            target=payload["target"],
                            mode=payload["mode"],
                            upstream_requirements=stage_state.get("requirements", {}),
                            upstream_architecture=stage_state.get("architecture_outline", {}),
                            upstream_implementation_plan=stage_state.get("implementation_plan", {}),
                        )
                    else:
                        out = self._run_make_delivery(
                            text=payload["text"],
                            history=payload["history"],
                            target=payload["target"],
                            mode=payload["mode"],
                            seed_artifact_text="",
                            upstream_requirements=stage_state.get("requirements", {}),
                            upstream_architecture=stage_state.get("architecture_outline", {}),
                            upstream_implementation_plan=stage_state.get("implementation_plan", {}),
                        )
                    scratch["worker_result"] = dict(out)
                    return {"worker_result": dict(out)}
                if stage == "verification":
                    out = scratch.get("worker_result", {}) if isinstance(scratch.get("worker_result", {}), dict) else {}
                    fallback = f"{out.get('message', 'Build pipeline completed.')} Output: {out.get('path', '')}"
                    reply = self._make_summary_reply(lane=payload["lane"], out=out, fallback=fallback)
                    reply = self._append_daymarker_note(reply, event_note)
                    reply = self._append_daymarker_note(reply, reminder_note)
                    final_reply = self._complete_turn(
                        user_text=payload["text"],
                        lane=("project" if payload["lane"] == "make_doc" else payload["lane"]),
                        reply_text=reply,
                        worker_result=out,
                        context_feedback=self._context_feedback(
                            user_text=payload["text"],
                            reply_text=reply,
                            household_context=household_context,
                        ),
                    )
                    scratch["reply"] = final_reply
                    return {"reply": final_reply}

            if pipeline_name == "code_fix_pipeline":
                if stage == "planner":
                    return {"plan": f"Apply deterministic fix flow for: {payload['text'][:220]}"}
                if stage == "code_localizer":
                    return {"candidate_files": []}
                if stage == "patch_writer":
                    return {"patch_text": "Delegated to build pipeline implementation path."}
                if stage == "reviewer":
                    return {"review_findings": []}
                if stage == "test_fixer":
                    return {"test_summary": "No dedicated test-fixer stage configured yet."}
                if stage == "finalizer":
                    # Reuse build pipeline generation path for now; deterministic stage order still enforced.
                    self._last_project_mode = self.pipeline_store.get(self.project_slug)
                    out = self._run_make_delivery(
                        text=payload["text"],
                        history=payload["history"],
                        target=payload["target"],
                        mode=payload["mode"],
                        seed_artifact_text="",
                    )
                    fallback = f"{out.get('message', 'Code-fix pipeline completed.')} Output: {out.get('path', '')}"
                    reply = self._make_summary_reply(lane=payload["lane"], out=out, fallback=fallback)
                    final_reply = self._complete_turn(
                        user_text=payload["text"],
                        lane=payload["lane"],
                        reply_text=reply,
                        worker_result=out,
                        context_feedback=self._context_feedback(
                            user_text=payload["text"],
                            reply_text=reply,
                            household_context=household_context,
                        ),
                    )
                    scratch["reply"] = final_reply
                    return {"reply": final_reply}

            return {}

        def _context_pack_builder(
            stage: str,
            stage_state: dict[str, Any],
            payload: dict[str, Any],
            run_id: str,
            pipeline: str,
        ) -> dict[str, Any]:
            kernel = self.project_kernel_store.snapshot(self.project_slug)
            combined_rows = self.cag_memory_store.list_rows_for_projects(
                projects=[self.project_slug, "general"],
                include_expired=False,
                include_superseded=False,
                limit=600,
            )
            project_rows = [row for row in combined_rows if str(row.get("project", "")).strip() == self.project_slug]
            domain_rows = [row for row in combined_rows if str(row.get("project", "")).strip() == "general"]
            memory_rows = self._select_context_memory_rows(
                self.cag_selector,
                payload=payload,
                project_rows=project_rows,
                domain_rows=domain_rows,
            )
            knowledge = kernel.get("knowledge_spine", {}) if isinstance(kernel.get("knowledge_spine", {}), dict) else {}
            thread = str(knowledge.get("thread", "")).strip()
            decision_rows = self.cag_decision_ledger.list_entries(
                project=self.project_slug,
                thread=thread,
                limit=180,
            )
            benchmark_lessons = []
            for row in memory_rows:
                row_type = str(row.get("type", row.get("memory_type", ""))).strip().lower()
                if row_type == "benchmark_implication":
                    text = str(row.get("text", "")).strip()
                    if text:
                        benchmark_lessons.append(text)

            hardware_token_budget = payload.get("hardware_token_budget")
            if hardware_token_budget is None:
                context_pack = payload.get("context_pack", {})
                if isinstance(context_pack, dict):
                    hardware_token_budget = context_pack.get("token_budget")
            try:
                parsed_budget = int(hardware_token_budget) if hardware_token_budget is not None else None
            except Exception:
                parsed_budget = None

            context_pack = self.context_compiler.compile(
                run_id=run_id,
                pipeline=pipeline,
                stage=stage,
                input_payload=dict(payload),
                stage_state=dict(stage_state),
                project_kernel=kernel,
                memory_rows=memory_rows,
                decision_rows=decision_rows,
                benchmark_lessons=benchmark_lessons,
                output_contract=contract_for_stage(stage).stage,
                hardware_token_budget=parsed_budget,
            )
            domain = str(payload.get("domain", "general_research")).strip() or "general_research"
            make_type = str(payload.get("target", payload.get("make_type", "model_runtime_system"))).strip() or "model_runtime_system"
            research_focus = str(payload.get("query_mode", "implementation_focused")).strip() or "implementation_focused"
            manifest = self.specialist_registry.manifest_for_stage(
                stage=stage,
                pipeline=pipeline,
                next_stage="",
                domain=domain,
                make_type=make_type,
                research_focus=research_focus,
            )
            context_pack["specialist_role"] = manifest.specialist_role
            context_pack["specialist_manifest"] = manifest.as_dict()
            return context_pack

        def _on_deck_planner(
            stage: str,
            stage_state: dict[str, Any],
            payload: dict[str, Any],
            run_id: str,
            pipeline: str,
            planner_context: dict[str, Any],
        ) -> dict[str, Any]:
            spec_stages = planner_context.get("spec_stages", [])
            if not isinstance(spec_stages, list):
                spec_stages = []
            current_context_pack = planner_context.get("current_context_pack", {})
            if not isinstance(current_context_pack, dict):
                current_context_pack = {}
            memory_state = payload.get("model_memory_state", {})
            if not isinstance(memory_state, dict):
                memory_state = {}
            return self.on_deck_runtime.plan_for_stage(
                stage=stage,
                stage_state=stage_state,
                payload=payload,
                run_id=run_id,
                pipeline=pipeline,
                spec_stages=[str(x).strip() for x in spec_stages if str(x).strip()],
                current_context_pack=current_context_pack,
                context_pack_builder=_context_pack_builder,
                memory_state=memory_state,
            )

        result = self.pipeline_engine.execute(
            spec=spec,
            input_payload=pipeline_context,
            stage_runner=_stage_runner,
            context_pack_builder=_context_pack_builder,
            on_deck_planner=_on_deck_planner,
            model_runtime=self.model_runtime,
        )
        try:
            stage_outputs = result.get("stage_outputs", {}) if isinstance(result.get("stage_outputs", {}), dict) else {}
            context_packs = result.get("context_packs", {}) if isinstance(result.get("context_packs", {}), dict) else {}
            stage_audits = result.get("stage_audits", {}) if isinstance(result.get("stage_audits", {}), dict) else {}
            stage_timings_ms = result.get("stage_timings_ms", {}) if isinstance(result.get("stage_timings_ms", {}), dict) else {}
            started_at = str(result.get("started_at", "")).strip()
            finished_at = str(result.get("finished_at", "")).strip()
            run_id = str(result.get("run_id", "")).strip()
            stage_rows = self.trace_ledger.build_stage_rows(
                stage_outputs=stage_outputs,
                context_packs=context_packs,
                stage_timings_ms=stage_timings_ms,
                stage_audits=stage_audits,
            )
            scores = [float(x.get("output_score", 0.0) or 0.0) for x in stage_rows]
            final_score = (sum(scores) / len(scores)) if scores else (1.0 if result.get("ok", False) else 0.0)
            promoted_memory_ids: list[str] = []
            gate_row = stage_outputs.get("cag_promotion_gate", {}) if isinstance(stage_outputs.get("cag_promotion_gate", {}), dict) else {}
            for value in gate_row.get("accepted_memory_ids", []) if isinstance(gate_row.get("accepted_memory_ids", []), list) else []:
                token = str(value).strip()
                if token:
                    promoted_memory_ids.append(token)
            contract_findings: list[str] = []
            for stage_name, audit_row in stage_audits.items():
                if not isinstance(audit_row, dict):
                    continue
                if not bool(audit_row.get("ok", False)):
                    missing = ",".join([str(x) for x in audit_row.get("missing_fields", []) if str(x).strip()])
                    forbidden = ",".join([str(x) for x in audit_row.get("forbidden_fields", []) if str(x).strip()])
                    finding = f"{stage_name}:contract_violation"
                    if missing:
                        finding += f":missing={missing}"
                    if forbidden:
                        finding += f":forbidden={forbidden}"
                    contract_findings.append(finding)

            lane_cfg = lane_model_config(self.repo_root, str(pipeline_context.get("lane", "")).strip())
            if not lane_cfg:
                lane_cfg = lane_model_config(self.repo_root, "orchestrator")
            model_name = str(lane_cfg.get("model", "unknown")).strip() or "unknown"
            trace_row = {
                "run_id": run_id,
                "project": self.project_slug,
                "pipeline": str(result.get("pipeline", pipeline_name)),
                "model": model_name,
                "stages": stage_rows,
                "final_score": float(final_score),
                "auditor_findings": list(contract_findings),
                "promoted_memories": list(promoted_memory_ids),
                "started_at": started_at,
                "finished_at": finished_at,
            }

            replay_row = {
                "run_id": run_id,
                "project": self.project_slug,
                "pipeline": str(result.get("pipeline", pipeline_name)),
                "model_settings": dict(lane_cfg or {}),
                "input_payload": dict(pipeline_context),
                "context_packs": dict(context_packs),
                "stage_outputs": dict(stage_outputs),
                "stage_audits": dict(stage_audits),
                "stage_timings_ms": dict(stage_timings_ms),
                "hardware_profile": hardware_profile_summary(self.hardware_profile),
                "promoted_memory_ids": list(promoted_memory_ids),
                "started_at": started_at,
                "finished_at": finished_at,
            }

            kernel = self.project_kernel_store.snapshot(self.project_slug)
            auditor_report = self.auditor_engine.audit_run(
                trace_row=trace_row,
                replay_row=replay_row,
                project_kernel=kernel,
            )
            typed_findings = [
                str(x.get("type", "")).strip()
                for x in auditor_report.get("typed_findings", [])
                if isinstance(x, dict) and str(x.get("type", "")).strip()
            ]
            merged_findings = list(contract_findings)
            for finding in typed_findings:
                if finding not in merged_findings:
                    merged_findings.append(finding)

            # rewrite trace with typed findings as the primary auditor signal
            trace_row = self.trace_ledger.record_run(
                run_id=run_id,
                project=self.project_slug,
                pipeline=str(result.get("pipeline", pipeline_name)),
                model=model_name,
                stages=stage_rows,
                final_score=float(final_score),
                auditor_findings=merged_findings,
                promoted_memories=promoted_memory_ids,
                started_at=started_at,
                finished_at=finished_at,
            )

            promoted_by_auditor: list[str] = []
            promote_enabled = str(os.getenv("OATHWEAVERX_AUDITOR_PROMOTE_BENCHMARK_LESSONS", "1")).strip().lower() not in {"0", "false", "off", "no"}
            if promote_enabled:
                scope_row = kernel.get("current_scope", {}) if isinstance(kernel.get("current_scope", {}), dict) else {}
                existing_benchmark_rows = self.cag_memory_store.list_rows(
                    project=self.project_slug,
                    memory_types=["benchmark_implication"],
                    include_expired=True,
                    include_superseded=True,
                    limit=500,
                )
                existing_texts = {
                    str(row.get("text", "")).strip().lower()
                    for row in existing_benchmark_rows
                    if isinstance(row, dict) and str(row.get("text", "")).strip()
                }
                for candidate in auditor_report.get("promotion_candidates", []) if isinstance(auditor_report.get("promotion_candidates", []), list) else []:
                    if not isinstance(candidate, dict):
                        continue
                    text = str(candidate.get("text", "")).strip()
                    if not text or text.lower() in existing_texts:
                        continue
                    persisted = self.cag_memory_store.add_row(
                        {
                            **dict(candidate),
                            "scope": str(scope_row.get("scope", "")).strip(),
                            "scope_level": str(scope_row.get("scope_level", "project")).strip() or "project",
                            "domain": str(scope_row.get("domain", "")).strip(),
                            "topic": str(scope_row.get("topic", "")).strip(),
                            "thread": str(scope_row.get("thread", "")).strip(),
                            "project": str(scope_row.get("project", self.project_slug)).strip() or self.project_slug,
                            "run": str(scope_row.get("run", "")).strip(),
                        }
                    )
                    memory_id = str(persisted.get("memory_id", "")).strip()
                    if memory_id:
                        promoted_by_auditor.append(memory_id)
                        promoted_memory_ids.append(memory_id)
                        existing_texts.add(text.lower())

            auditor_report["promoted_memory_ids"] = list(promoted_by_auditor)
            auditor_report = self.regression_reporter.write_report(auditor_report)
            watchtower_scan: dict[str, Any] = {}
            watchtower_scan_enabled = str(os.getenv("OATHWEAVERX_WATCHTOWER_SCAN_ENABLED", "1")).strip().lower() not in {"0", "false", "off", "no"}
            if watchtower_scan_enabled:
                try:
                    watchtower_scan = self.watchtower.scan_project_gaps(
                        project=self.project_slug,
                        project_kernel=kernel,
                        auditor_report=auditor_report,
                    )
                except Exception as scan_exc:
                    watchtower_scan = {"error": str(scan_exc)}

            replay_row = self.replay_store.save_bundle(
                run_id=run_id,
                project=self.project_slug,
                pipeline=str(result.get("pipeline", pipeline_name)),
                model_settings=dict(lane_cfg or {}),
                input_payload=dict(pipeline_context),
                context_packs=context_packs,
                stage_outputs=stage_outputs,
                stage_audits=stage_audits,
                stage_timings_ms=stage_timings_ms,
                hardware_profile=hardware_profile_summary(self.hardware_profile),
                promoted_memory_ids=promoted_memory_ids,
                started_at=started_at,
                finished_at=finished_at,
            )

            self.capability_registry.record_run_observation(
                claim_text="8B + CAG + pipeline can approach 70B quality on long-running architecture work",
                run_id=run_id,
                pipeline=str(result.get("pipeline", pipeline_name)),
                final_score=float(final_score),
                benchmark_id="cag_long_project_v3",
                status="hypothesis",
            )
            if isinstance(details_sink, dict):
                details_sink["trace_ledger"] = dict(trace_row)
                details_sink["replay_bundle"] = {
                    "run_id": str(replay_row.get("run_id", "")),
                    "pipeline": str(replay_row.get("pipeline", "")),
                    "created_at": str(replay_row.get("created_at", "")),
                }
                details_sink["auditor_report"] = {
                    "run_id": str(auditor_report.get("run_id", "")),
                    "typed_findings": [str(x.get("type", "")) for x in auditor_report.get("typed_findings", []) if isinstance(x, dict)],
                    "proposed_system_changes": list(auditor_report.get("proposed_system_changes", [])),
                    "promoted_memory_ids": list(auditor_report.get("promoted_memory_ids", [])),
                }
                details_sink["watchtower_scan"] = dict(watchtower_scan)
        except Exception as exc:
            if isinstance(details_sink, dict):
                details_sink["trace_ledger_error"] = str(exc)
        if isinstance(details_sink, dict):
            details_sink["pipeline_run"] = dict(result)
        final_output = result.get("final_output", {}) if isinstance(result.get("final_output", {}), dict) else {}
        reply = str(final_output.get("reply", "")).strip() or str(scratch.get("reply", "")).strip()
        if reply:
            return reply
        if result.get("ok", False):
            return None
        return f"Pipeline execution failed: {result.get('error', 'unknown error')}."

    @staticmethod
    def _sort_memory_rows_oldest_first(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
        def _key(row: dict[str, Any]) -> str:
            return str(row.get("created_at", "")).strip() or str(row.get("updated_at", "")).strip()

        return sorted([dict(x) for x in rows if isinstance(x, dict)], key=_key)

    def _build_cag_candidate(
        self,
        *,
        text: str,
        payload: dict[str, Any],
        scope_row: dict[str, Any],
        web_details: Any,
    ) -> dict[str, Any]:
        summary = str(text or "").strip()
        if not summary:
            return {}
        source_count = 0
        if isinstance(web_details, dict):
            source_count = int(web_details.get("source_count", 0) or 0)
        row_type = self._infer_memory_type(summary, payload)
        tags = self._candidate_tags(payload, scope_row)
        promoted_terms = self._promoted_terms(summary, limit=12)
        confidence = 0.55
        if source_count > 0:
            confidence += 0.15
        if str(payload.get("query_complexity", "")).strip().lower() == "deep":
            confidence += 0.05
        confidence = max(0.0, min(1.0, confidence))
        evidence = [
            {"kind": "pipeline_stage", "value": "synthesis"},
            {"kind": "lane", "value": str(payload.get("lane", ""))},
            {"kind": "source_count", "value": source_count},
        ]
        validation = {
            "task_metadata": True,
            "has_citation": source_count > 0,
            "auditor_approved": source_count > 0,
            "user_accepted": False,
            "tests_passed": False,
            "benchmark_backed": row_type == "benchmark_implication",
        }
        return {
            "text": summary,
            "scope": str(scope_row.get("scope", "")).strip(),
            "scope_level": str(scope_row.get("scope_level", "project")).strip() or "project",
            "domain": str(scope_row.get("domain", "")).strip(),
            "topic": str(scope_row.get("topic", "")).strip(),
            "thread": str(scope_row.get("thread", "")).strip(),
            "project": str(scope_row.get("project", self.project_slug)).strip() or self.project_slug,
            "run": str(scope_row.get("run", "")).strip(),
            "type": row_type,
            "status": "candidate",
            "human_status": "unreviewed",
            "evidence": evidence,
            "supersedes": [],
            "superseded_by": [],
            "confidence": confidence,
            "tags": tags,
            "promoted_terms": promoted_terms,
            "source": "cag_promotion_gate",
            "validation": validation,
            "expires_at": "",
        }

    @staticmethod
    def _candidate_tags(payload: dict[str, Any], scope_row: dict[str, Any]) -> list[str]:
        return _cag_helpers.candidate_tags(payload, scope_row)

    @staticmethod
    def _promoted_terms(text: str, *, limit: int = 12) -> list[str]:
        return _cag_helpers.promoted_terms(text, limit=limit)

    @staticmethod
    def _infer_memory_type(summary: str, payload: dict[str, Any]) -> str:
        return _cag_helpers.infer_memory_type(summary, payload)

    def plan_message(self, text: str) -> dict[str, Any]:
        plan = self.turn_planner.plan(
            text,
            project=self.project_slug,
            client=self.ollama,
            model_cfg=lane_model_config(self.repo_root, "orchestrator_reasoning"),
        ).as_dict()
        plan["project_kernel"] = self.project_kernel_store.snapshot(self.project_slug)
        return plan

    def reload_models(self) -> str:
        self.model_routing = load_model_routing(self.repo_root)
        self._infra.reset()
        self._tool_registry = None
        return "Model routing reloaded."

    def models_text(self) -> str:
        if not self.model_routing:
            return "No model routing config found."
        lines = ["Model routing:"]
        for lane, cfg in self.model_routing.items():
            model = cfg.get("model", "unknown")
            purpose = cfg.get("purpose", "")
            parallel_agents = cfg.get("parallel_agents")
            if parallel_agents is None:
                lines.append(f"- {lane}: {model} ({purpose})")
            else:
                lines.append(f"- {lane}: {model} ({purpose}; workers={parallel_agents})")
        return "\n".join(lines)

    def local_models_text(self) -> str:
        try:
            models = self.ollama.list_local_models()
        except Exception as exc:
            return f"Could not query local Ollama models: {exc}"
        if not models:
            return "No local Ollama models found."
        lines = ["Local Ollama models:"]
        lines.extend([f"- {name}" for name in models])
        return "\n".join(lines)

    def _chat_via_graph_enabled(self) -> bool:
        routing = self.model_routing if isinstance(self.model_routing, dict) else {}
        nested = routing.get("orchestrator", {}) if isinstance(routing.get("orchestrator", {}), dict) else {}
        raw = routing.get("orchestrator.chat_via_graph", nested.get("chat_via_graph", False))
        return bool(raw)

    def set_project(self, slug: str) -> str:
        self.project_slug = slug.strip().replace(" ", "_")
        mode_info = self.pipeline_store.get(self.project_slug)
        kernel = self.project_kernel_store.get_or_create(self.project_slug)
        self.bus.emit(
            "orchestrator",
            "project_switched",
            {
                "project": self.project_slug,
                "project_mode": mode_info.get("mode", "discovery"),
                "project_topic_type": mode_info.get("topic_type", "general"),
                "project_target": mode_info.get("target", "auto"),
                "domain": kernel.knowledge_spine.domain,
                "thread": kernel.knowledge_spine.thread,
                "pipeline": kernel.execution_spine.pipeline,
            },
        )
        return f"Active project set to '{self.project_slug}'."

    def project_mode_snapshot(self, project: str | None = None) -> dict[str, Any]:
        active_project = project or self.project_slug
        row = self.pipeline_store.get(active_project)
        row["project_kernel"] = self.project_kernel_store.snapshot(active_project)
        return row

    def set_project_mode(
        self,
        *,
        project: str | None = None,
        mode: str | None = None,
        target: str | None = None,
        topic_type: str | None = None,
    ) -> dict[str, Any]:
        row = self.pipeline_store.set(project or self.project_slug, mode=mode, target=target, topic_type=topic_type)
        active_project = str(row.get("project", self.project_slug)).strip() or self.project_slug
        lane_hint = "make_app" if str(row.get("mode", "discovery")) == "make" else "research"
        self.project_kernel_store.update_for_turn(
            project_id=active_project,
            lane=lane_hint,
            topic_type=str(row.get("topic_type", "general")),
            query_text="",
            query_mode="general_research",
            make_type=str(row.get("target", "auto")),
            make_intent=str(row.get("mode", "discovery")),
            specialist_stages=[],
        )
        self.bus.emit(
            "orchestrator",
            "project_mode_changed",
            {
                "project": row.get("project", self.project_slug),
                "mode": row.get("mode", "discovery"),
                "topic_type": row.get("topic_type", "general"),
                "target": row.get("target", "auto"),
            },
        )
        return row

    def set_web_mode(self, mode: str) -> str:
        try:
            value = self.web_engine.set_mode(mode)
        except ValueError as exc:
            return str(exc)
        self.bus.emit("orchestrator", "web_mode_changed", {"mode": value, "project": self.project_slug})
        return f"Web research mode set to '{value}'."

    def set_web_provider(self, provider: str) -> str:
        try:
            value = self.web_engine.set_provider(provider)
        except ValueError as exc:
            return str(exc)
        self.bus.emit("orchestrator", "web_provider_changed", {"provider": value, "project": self.project_slug})
        return f"Web research provider set to '{value}'."

    def web_mode_text(self) -> str:
        return self.web_engine.mode_text()

    def web_provider_text(self) -> str:
        return self.web_engine.provider_text()

    def web_sources_text(self, limit: int = 10) -> str:
        return self.web_engine.sources_text(project=self.project_slug, limit=limit)

    def set_cloud_mode(self, mode: str) -> str:
        return "Cloud integrations are disabled in this build."

    def cloud_mode_text(self) -> str:
        return "Cloud integrations are disabled in this build."

    def cloud_runs_text(self, limit: int = 10) -> str:
        return "Cloud integrations are disabled in this build."

    def set_external_tools_mode(self, mode: str) -> str:
        try:
            value = self.external_tools_settings.set_mode(mode)
        except ValueError as exc:
            return str(exc)
        self.bus.emit(
            "orchestrator",
            "external_tools_mode_changed",
            {"mode": value, "project": self.project_slug},
        )
        return f"External tools mode set to '{value}'."

    def external_tools_mode_text(self) -> str:
        return self.external_tools_settings.mode_text()

    def project_facts_text(self) -> str:
        text = self.project_memory.summary_text(self.project_slug, limit_chars=2600)
        if text.strip():
            return text
        return f"No stored project facts yet for '{self.project_slug}'."

    def clear_project_facts(self) -> str:
        removed = self.project_memory.clear_project(self.project_slug)
        if removed:
            return f"Cleared stored project facts for '{self.project_slug}'."
        return f"No stored project facts found for '{self.project_slug}'."

    def refresh_project_facts(
        self,
        *,
        history: list[dict[str, str]] | None = None,
        reset: bool = True,
    ) -> str:
        result = self.project_memory.refresh_from_history(self.project_slug, history, reset=reset)
        return (
            f"Project fact refresh complete for '{self.project_slug}'.\n"
            f"- scanned_user_messages: {result.get('scanned_user_messages', 0)}\n"
            f"- updated_fields: {result.get('updated_fields', 0)}\n"
            f"- facts_now: {result.get('facts_count', 0)}\n"
            f"- updated_at: {result.get('updated_at', '') or 'n/a'}"
        )

    def improvement_status_text(self) -> str:
        return self.improvement_engine.status_text(self.project_slug)

    def improvement_run_now(self, *, history: list[dict[str, str]] | None = None) -> str:
        rows = history if isinstance(history, list) else []
        if not rows:
            return (
                "Continuous improvement refresh skipped: no user history was available to parse.\n"
                "Send a few normal messages first, then run /improve-now."
            )
        result = self.project_memory.refresh_from_history(self.project_slug, rows, reset=False)
        self.improvement_engine.note_fact_refresh(
            project=self.project_slug,
            reason="manual_improve_now",
            refresh_result=result,
        )
        self.bus.emit(
            "orchestrator",
            "continuous_improve_manual_refresh",
            {
                "project": self.project_slug,
                "scanned_user_messages": result.get("scanned_user_messages", 0),
                "updated_fields": result.get("updated_fields", 0),
                "facts_count": result.get("facts_count", 0),
            },
        )
        return (
            f"Continuous improvement refresh complete for '{self.project_slug}'.\n"
            f"- scanned_user_messages: {result.get('scanned_user_messages', 0)}\n"
            f"- updated_fields: {result.get('updated_fields', 0)}\n"
            f"- facts_now: {result.get('facts_count', 0)}\n"
            f"- updated_at: {result.get('updated_at', '') or 'n/a'}"
        )

    def status_text(self) -> str:
        return _build_status_text(
            project_slug=self.project_slug,
            activity_store=self.activity_store,
            approval_gate=self.approval_gate,
            handoff_queue=self.handoff_queue,
            learning_engine=self.learning_engine,
            reflection_engine=self.reflection_engine,
            web_engine=self.web_engine,
            external_tools_settings=self.external_tools_settings,
            external_request_store=self.external_request_store,
            project_memory=self.project_memory,
            pipeline_store=self.pipeline_store,
            improvement_engine=self.improvement_engine,
        )

    def activity_text(self, limit: int = 20) -> str:
        return self.activity_store.recent_text(limit=limit)

    def lanes_text(self, window: int = 200) -> str:
        return self.activity_store.lane_stats_text(window=window)

    def artifacts_text(self, limit: int = 20) -> str:
        return self.activity_store.artifacts_text(limit=limit)

    # Oathweaver alias/identity constants — canonical source is oathweaver/identity.py
    _OATHWEAVER_ALIASES: tuple[str, ...] = OATHWEAVER_ALIASES
    _OATHWEAVER_ADDRESS_NEXT_WORDS: frozenset[str] = OATHWEAVER_ADDRESS_NEXT_WORDS
    _OATHWEAVER_IDENTITY_CUES: tuple[str, ...] = OATHWEAVER_IDENTITY_CUES
    # Recency detection constant — canonical source is text_processing/text_analysis.py
    _RECENCY_TERMS: frozenset[str] = RECENCY_TERMS

    def _load_manifesto_text(self, max_chars: int = 20000) -> str:
        cache = {"_mtime": self._manifesto_cache_mtime, "_text": self._manifesto_cache_text}
        text = _load_manifesto(
            repo_root=self.repo_root,
            manifesto_path=getattr(self, "manifesto_path", None),
            cache=cache,
            max_chars=max_chars,
        )
        self._manifesto_cache_mtime = cache["_mtime"]
        self._manifesto_cache_text = cache["_text"]
        return text

    def _manifesto_principles_block(self) -> str:
        return _manifesto_principles(self._load_manifesto_text(max_chars=14000))

    def _oathweaver_persona_block(self) -> str:
        return _gb_persona_block(self._load_manifesto_text(max_chars=14000))

    def _weaver_persona_block(self) -> str:
        return _weaver_persona_block(self._load_manifesto_text(max_chars=14000))

    def _oathweaver_identity_reply(self) -> str:
        return _gb_identity_reply(self._load_manifesto_text(max_chars=14000))

    def _chat_layer_config(self) -> dict[str, Any]:
        cfg = lane_model_config(self.repo_root, "chat_layer")
        if cfg:
            return cfg
        return lane_model_config(self.repo_root, "conversation_layer")

    @staticmethod
    def _heuristic_surface_polish(text: str) -> str:
        raw = str(text or "").strip()
        if not raw:
            return ""
        polished = raw.replace("\r\n", "\n")
        polished = re.sub(r"[ \t]+\n", "\n", polished)
        polished = re.sub(r"\n{3,}", "\n\n", polished)
        polished = re.sub(r"([,;:!?])([A-Za-z0-9])", r"\1 \2", polished)
        polished = re.sub(r"(?<=[A-Za-z])([.?!])([A-Z])", r"\1 \2", polished)
        polished = re.sub(r"\s+([,;:!?])", r"\1", polished)
        polished = re.sub(r"(?<!\.)\s+\.", ".", polished)
        polished = re.sub(r"[ \t]{2,}", " ", polished)
        return polished.strip()

    @staticmethod
    def _strip_web_source_provenance(text: str) -> str:
        body = str(text or "").strip()
        if not body:
            return ""
        cleaned = body
        cleaned = re.sub(
            r"(?i)\bbased on (?:the )?(?:links|urls?) (?:you )?(?:provided|gave(?: me)?)\b",
            "based on the cited sources",
            cleaned,
        )
        cleaned = re.sub(
            r"(?i)\bfrom (?:the )?(?:links|urls?) (?:you )?(?:provided|gave(?: me)?)\b",
            "from the cited sources",
            cleaned,
        )
        cleaned = re.sub(
            r"(?i)\b(?:these|the)\s+(?:web\s+)?(?:sources?|source snippets?|urls?)\s+(?:were|was)\s+"
            r"(?:fetched|retrieved|pulled|scraped)\s+(?:autonomously|automatically)?"
            r"(?:\s+by\s+the\s+system(?:'s)?\s+web\s+crawler)?"
            r"(?:\s*[—-]\s*the user did not provide(?:\s+them|\s+any\s+links?\s+or\s+urls?)?)?\b\.?",
            "",
            cleaned,
        )
        cleaned = re.sub(r"(?i)\bit\s+was\s+not\s+provided\s+by\s+the\s+user\b\.?", "", cleaned)
        cleaned = re.sub(r"(?i)\bthe user did not provide(?:\s+any)?\s+(?:links?|urls?|sources?)\b\.?", "", cleaned)
        cleaned = re.sub(r"(?i)\bit is not the user's browsing activity\b\.?", "", cleaned)
        cleaned = re.sub(r"[ \t]+\n", "\n", cleaned)
        cleaned = re.sub(r"\n{3,}", "\n\n", cleaned)
        cleaned = re.sub(r"[ \t]{2,}", " ", cleaned)
        cleaned = re.sub(r"\s+([,;:.!?])", r"\1", cleaned)
        cleaned = re.sub(r"([.!?])\s*(?:[.!?]\s*)+", r"\1 ", cleaned)
        return cleaned.strip()

    def _surface_polish_reply(self, text: str) -> str:
        raw = self._strip_web_source_provenance(text)
        if not raw:
            return ""
        heuristic = self._heuristic_surface_polish(raw)
        heuristic = self._strip_web_source_provenance(heuristic)
        if not heuristic:
            return raw
        if any(token in heuristic for token in _SURFACE_POLISH_SKIP_TOKENS):
            return heuristic
        if len(heuristic) > 3200:
            return heuristic

        cfg = lane_model_config(self.repo_root, "orchestrator_reasoning")
        model = str(cfg.get("model", "")).strip() or "deepseek-r1:8b"
        fallback_models = cfg.get("fallback_models", []) if isinstance(cfg.get("fallback_models", []), list) else ["hf.co/unsloth/Qwen3-8B-GGUF:UD-Q5_K_XL"]
        system_prompt = (
            "You are doing a light copyedit pass on assistant text. "
            "Fix only obvious spelling, spacing, punctuation, and capitalization issues. "
            "Preserve wording, tone, structure, markdown, bullets, and meaning. "
            "Do not add facts, remove content, or rewrite for style. "
            "Return only the edited text."
        )
        try:
            polished = self.ollama.chat(
                model=model,
                system_prompt=system_prompt,
                user_prompt=heuristic,
                temperature=0.0,
                num_ctx=min(int(cfg.get("num_ctx", 16384) or 16384), 8192),
                think=False,
                timeout=min(int(cfg.get("timeout_sec", 180) or 180), 90),
                retry_attempts=1,
                retry_backoff_sec=0.5,
                fallback_models=fallback_models,
            )
            polished = self._strip_web_source_provenance(polished)
            if not polished:
                return heuristic
            if abs(len(polished) - len(heuristic)) > max(120, int(len(heuristic) * 0.35)):
                return heuristic
            return polished
        except Exception:
            return heuristic

    def _mentions_oathweaver_alias(self, text: str) -> bool:
        return mentions_oathweaver_alias(text)

    @staticmethod
    def _is_lightweight_social(text: str) -> bool:
        """Return True for short social/acknowledgment messages that skip heavy context."""
        clean = text.strip().rstrip("!?.,").lower().strip()
        if clean in _SOCIAL_PATTERNS:
            return True
        words = clean.split()
        if len(words) <= 3 and any(w in _SOCIAL_PATTERNS for w in words):
            return True
        return False

    @staticmethod
    def _dedup_forage_tags(text: str) -> str:
        """Keep only the first [FORAGE:] tag; strip all subsequent ones."""
        kept = False
        def _keep_first(m: re.Match) -> str:
            nonlocal kept
            if kept:
                return ""
            kept = True
            return m.group(0)
        return re.sub(r'\n?\[FORAGE:\s*"[^"]+"\]', _keep_first, text).strip()

    def _forage_log_path(self) -> Path:
        path = self.repo_root / "Runtime" / "state" / "forage_log.jsonl"
        path.parent.mkdir(parents=True, exist_ok=True)
        if not path.exists():
            path.write_text("", encoding="utf-8")
        return path

    @staticmethod
    def _normalize_forage_seed(seed: str) -> str:
        return " ".join(str(seed or "").strip().lower().split())

    @staticmethod
    def _forage_refresh_override(seed: str) -> bool:
        low = str(seed or "").lower()
        return "refresh" in low or "again" in low

    def _read_forage_log(self, *, limit: int = 400) -> list[dict[str, Any]]:
        path = self._forage_log_path()
        rows: list[dict[str, Any]] = []
        for line in path.read_text(encoding="utf-8", errors="ignore").splitlines():
            text = line.strip()
            if not text:
                continue
            try:
                payload = json.loads(text)
            except Exception:
                continue
            if isinstance(payload, dict):
                rows.append(payload)
        if len(rows) > limit:
            rows = rows[-limit:]
        return rows

    def _append_forage_log(self, payload: dict[str, Any]) -> None:
        row = dict(payload)
        row.setdefault("ts", datetime.now(timezone.utc).isoformat())
        with self._forage_log_path().open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(row, ensure_ascii=True) + "\n")

    def _latest_research_summary_path(self) -> str:
        root = self.repo_root / "Projects" / (self.project_slug.strip() or "general") / "research_summaries"
        if not root.exists():
            return ""
        rows = sorted(root.glob("*.md"), key=lambda p: p.stat().st_mtime, reverse=True)
        if not rows:
            return ""
        return str(rows[0])

    def _read_activity_text(self, path_text: str, *, max_chars: int) -> tuple[str, float]:
        raw = str(path_text or "").strip()
        if not raw:
            return "", 0.0
        try:
            path = Path(raw)
        except Exception:
            return "", 0.0
        if not path.is_absolute():
            path = self.repo_root / path
        try:
            if not path.exists() or not path.is_file():
                return "", 0.0
            text = path.read_text(encoding="utf-8", errors="ignore")
            if len(text) > max_chars:
                text = text[:max_chars]
            mtime = float(path.stat().st_mtime)
            return text.strip(), mtime
        except Exception:
            return "", 0.0

    def _project_research_brief(
        self,
        project_slug: str,
        *,
        query: str,
        max_chars: int = 1200,
    ) -> dict[str, Any]:
        project = str(project_slug or "").strip() or "general"
        rows = self.activity_store.rows()
        candidates: list[dict[str, Any]] = []
        for row in rows:
            details = row.get("details") if isinstance(row, dict) else {}
            if not isinstance(details, dict):
                continue
            if str(details.get("project", "")).strip() != project:
                continue
            summary_path = str(details.get("summary_path", "")).strip()
            if not summary_path:
                continue
            if str(row.get("actor", "")).strip() != "research_pool":
                continue
            if str(row.get("event", "")).strip() != "completed":
                continue
            candidates.append(
                {
                    "ts": str(row.get("ts", "")).strip(),
                    "summary_path": summary_path,
                    "raw_path": str(details.get("raw_path", "")).strip(),
                }
            )
        candidates.sort(key=lambda item: str(item.get("ts", "")), reverse=True)

        loaded: list[dict[str, Any]] = []
        max_mtime = 0.0
        for item in candidates[:8]:
            summary_text, summary_mtime = self._read_activity_text(
                str(item.get("summary_path", "")),
                max_chars=1200,
            )
            raw_text, raw_mtime = self._read_activity_text(
                str(item.get("raw_path", "")),
                max_chars=900,
            )
            if not summary_text and not raw_text:
                continue
            max_mtime = max(max_mtime, summary_mtime, raw_mtime)
            loaded.append(
                {
                    "ts": str(item.get("ts", "")).strip(),
                    "summary": summary_text,
                    "raw": raw_text,
                }
            )
        cache_key = (project, max_mtime, int(max_chars))
        cached = self._project_research_brief_cache.get(cache_key)
        if isinstance(cached, dict):
            return dict(cached)

        raw_excerpts: list[str] = []
        if loaded:
            lines = [f"Research summaries for project {project}:"]
            remaining = max_chars - len(lines[0]) - 1
            for item in loaded[:5]:
                day = str(item.get("ts", ""))[:10]
                preview = " ".join(str(item.get("summary", "")).split())[:250]
                if not preview:
                    continue
                line = f"- {day}: {preview}"
                if remaining <= 0:
                    break
                if len(line) > remaining:
                    line = line[: max(0, remaining)].rstrip()
                if not line:
                    break
                lines.append(line)
                remaining -= len(line) + 1
            brief_text = "\n".join(lines).strip()
            for item in loaded:
                raw_preview = " ".join(str(item.get("raw", "")).split())
                if not raw_preview:
                    continue
                raw_excerpts.append(raw_preview[:600])
                if len(raw_excerpts) >= 2:
                    break
        else:
            fallback = str(self.project_memory.summary_text(project, limit_chars=max_chars) or "").strip()
            if fallback:
                brief_text = f"Research summaries for project {project}:\n{fallback}"
            else:
                brief_text = ""

        payload = {"brief": brief_text, "raw_excerpts": raw_excerpts, "query": str(query or "").strip()}
        self._project_research_brief_cache.clear()
        self._project_research_brief_cache[cache_key] = dict(payload)
        return payload

    def _reply_to_research_summary_context(
        self,
        reply_to: dict[str, Any] | None,
        *,
        max_chars: int = 4000,
    ) -> str:
        if not isinstance(reply_to, dict):
            return ""
        role = str(reply_to.get("role", "")).strip().lower()
        mode = str(reply_to.get("mode", "")).strip().lower()
        if role != "assistant":
            return ""
        if mode not in {"command", "forage", "research"}:
            return ""
        summary_path = str(reply_to.get("summary_path", "")).strip()
        if not summary_path:
            return ""
        summary_text, _mtime = self._read_activity_text(summary_path, max_chars=max_chars)
        if not summary_text:
            return ""
        display_path = summary_path
        try:
            display_path = str(Path(summary_path).relative_to(self.repo_root))
        except Exception:
            pass
        return (
            "Research summary tied to the replied-to message:\n"
            f"Path: {display_path}\n"
            f"{summary_text}"
        ).strip()

    def _project_make_brief(
        self,
        project_slug: str,
        *,
        max_items: int = 5,
        max_chars: int = 900,
    ) -> str:
        from orchestrator.services.make_catalog import label_for_type

        project = str(project_slug or "").strip() or "general"
        rows = self.activity_store.rows()
        candidates: list[dict[str, Any]] = []
        for row in rows:
            details = row.get("details") if isinstance(row, dict) else {}
            if not isinstance(details, dict):
                continue
            if str(details.get("project", "")).strip() != project:
                continue
            if str(row.get("event", "")).strip() != "make_deliverable_written":
                continue
            path = str(details.get("path", "")).strip()
            if not path:
                continue
            kind = str(details.get("kind") or details.get("make_type") or "").strip().lower()
            candidates.append(
                {
                    "ts": str(row.get("ts", "")).strip(),
                    "path": path,
                    "kind": kind,
                    "topic": str(details.get("topic", "")).strip(),
                }
            )
        candidates.sort(key=lambda item: str(item.get("ts", "")), reverse=True)

        loaded: list[dict[str, Any]] = []
        max_mtime = 0.0
        for item in candidates[: max(1, max_items)]:
            body, mtime = self._read_activity_text(str(item.get("path", "")), max_chars=520)
            max_mtime = max(max_mtime, mtime)
            if not body and not str(item.get("topic", "")).strip():
                continue
            loaded.append(
                {
                    **item,
                    "body": body,
                }
            )
        cache_key = (project, max_mtime, int(max_items), int(max_chars))
        cached = self._project_make_brief_cache.get(cache_key)
        if isinstance(cached, str):
            return cached

        if not loaded:
            return ""
        lines = [f"Recent Make outputs for project {project}:"]
        remaining = max_chars - len(lines[0]) - 1
        for item in loaded:
            kind = str(item.get("kind", "")).strip()
            label = label_for_type(kind) if kind else "Make Output"
            title = str(item.get("topic", "")).strip()
            if not title:
                try:
                    title = Path(str(item.get("path", ""))).stem.replace("_", " ").strip()
                except Exception:
                    title = ""
            preview = " ".join(str(item.get("body", "")).split())[:120]
            day = str(item.get("ts", ""))[:10]
            line = f"- [{label}] {title or label} ({day}): {preview}"
            if remaining <= 0:
                break
            if len(line) > remaining:
                line = line[: max(0, remaining)].rstrip()
            if not line:
                break
            lines.append(line)
            remaining -= len(line) + 1
        brief = "\n".join(lines).strip()
        self._project_make_brief_cache.clear()
        self._project_make_brief_cache[cache_key] = brief
        return brief

    @staticmethod
    def _merge_make_seed_context(research_context: str, seed_artifact_text: str) -> str:
        base = str(research_context or "").strip()
        seed = str(seed_artifact_text or "").strip()
        if not seed:
            return base
        if not base:
            return seed
        return f"{seed}\n\n{base}"

    def _forage_gate(self, seed: str) -> dict[str, Any]:
        now = datetime.now(timezone.utc)
        norm_seed = self._normalize_forage_seed(seed)
        override = self._forage_refresh_override(seed)
        rows = self._read_forage_log(limit=600)
        executed: list[dict[str, Any]] = []
        for row in rows:
            if str(row.get("project", "")).strip() != self.project_slug:
                continue
            if str(row.get("status", "")).strip() != "executed":
                continue
            ts_raw = str(row.get("ts", "")).strip()
            try:
                ts = datetime.fromisoformat(ts_raw.replace("Z", "+00:00"))
                if ts.tzinfo is None:
                    ts = ts.replace(tzinfo=timezone.utc)
            except Exception:
                continue
            executed.append({**row, "_ts": ts.astimezone(timezone.utc)})

        recent_10m = [
            row for row in executed
            if (now - row["_ts"]).total_seconds() <= 10 * 60
        ]
        if len(recent_10m) >= 3:
            return {
                "allowed": False,
                "reason": "rate_limit",
                "seed_norm": norm_seed,
                "prior": recent_10m[-1] if recent_10m else None,
            }

        if not override and norm_seed:
            for row in reversed(executed):
                row_seed = self._normalize_forage_seed(str(row.get("seed_norm", "") or row.get("seed", "")))
                if row_seed != norm_seed:
                    continue
                age_sec = (now - row["_ts"]).total_seconds()
                if age_sec <= 60 * 60:
                    return {
                        "allowed": False,
                        "reason": "dedup",
                        "seed_norm": norm_seed,
                        "prior": row,
                    }
                break

        return {
            "allowed": True,
            "reason": "",
            "seed_norm": norm_seed,
            "prior": None,
        }

    @staticmethod
    def _is_casual_conversation_turn(text: str) -> bool:
        """Return True for ordinary back-and-forth that should stay with weaver layer."""
        clean = " ".join(str(text or "").strip().lower().split())
        if not clean:
            return False
        if OathweaverOrchestrator._is_lightweight_social(clean):
            return True
        if any(phrase in clean for phrase in _CASUAL_CONVERSATION_PHRASES):
            return True
        if len(clean.split()) <= 10 and clean.endswith(("lol", "lmao", "haha", "ha")):
            return True
        return False

    def _strip_oathweaver_vocative_prefix(self, text: str) -> str:
        return _strip_vocative_prefix(text)

    def _is_oathweaver_self_query(self, text: str) -> bool:
        return _is_gb_self_query(text)

    def _build_self_state_block(
        self,
        text: str,
        *,
        role_scope: str = "owner",
    ) -> tuple[str, dict[str, Any]]:
        if not hasattr(self, "self_query_gate") or not hasattr(self, "self_state_service"):
            return "", {}
        try:
            decision = self.self_query_gate.classify(text)
        except Exception:
            return "", {}
        if not bool(getattr(decision, "is_self_query", False)):
            return "", {
                "is_self_query": False,
                "match_kind": "",
                "confidence": float(getattr(decision, "confidence", 0.0) or 0.0),
                "matched_exemplar": str(getattr(decision, "matched_exemplar", "") or ""),
            }
        try:
            snapshot = self.self_state_service.compute(
                match_kind=str(decision.match_kind or "general"),
                role=role_scope,
            )
            block = snapshot.to_prompt_block(str(decision.match_kind or "general"))
            return block, {
                "is_self_query": True,
                "match_kind": str(decision.match_kind or "general"),
                "confidence": float(decision.confidence),
                "matched_exemplar": str(decision.matched_exemplar or ""),
                "top_values": snapshot.top_values(str(decision.match_kind or "general")),
            }
        except Exception:
            return "", {}

    @staticmethod
    def _reply_contains_any_value(reply: str, values: list[str]) -> bool:
        hay = str(reply or "").strip().lower()
        if not hay:
            return False
        for value in values:
            needle = str(value or "").strip().lower()
            if needle and needle in hay:
                return True
        return False

    def _apply_self_state_safety_net(
        self,
        reply: str,
        *,
        self_query_meta: dict[str, Any] | None = None,
    ) -> str:
        text = str(reply or "").strip()
        meta = self_query_meta if isinstance(self_query_meta, dict) else {}
        if not bool(meta.get("is_self_query", False)):
            return text
        if float(meta.get("confidence", 0.0) or 0.0) < 0.85:
            return text
        kind = str(meta.get("match_kind", "")).strip().lower() or "general"
        values = [str(x).strip() for x in (meta.get("top_values") or []) if str(x).strip()]
        if values and self._reply_contains_any_value(text, values):
            return text
        lines = ["", "---", "For reference, current configuration:"]
        if kind == "model":
            if values:
                lines.append(f"- chat_layer.model: {values[0]}")
        elif kind == "hardware":
            if len(values) > 0:
                lines.append(f"- hardware_profile.name: {values[0]}")
            if len(values) > 1:
                lines.append(f"- hardware_profile.gpu_backend: {values[1]}")
        elif kind == "backend":
            if values:
                lines.append(f"- backend.reachable: {values[0]}")
        elif kind == "loaded":
            if values:
                lines.append(f"- loaded_models[0]: {values[0]}")
        else:
            if len(values) > 0:
                lines.append(f"- chat_layer.model: {values[0]}")
            if len(values) > 1:
                lines.append(f"- hardware_profile.name: {values[1]}")
        if len(lines) <= 3:
            return text
        return (text + "\n" + "\n".join(lines)).strip()

    def conversation_reply(
        self,
        text: str,
        *,
        history: list[dict[str, str]] | None = None,
        capture_history: list[dict[str, str]] | None = None,
        project: str | None = None,
        persona_override: str | None = None,
        progress_callback=None,
        details_sink: dict[str, Any] | None = None,
        cancel_checker=None,
        topic_context: str = "",
        reply_to: dict[str, Any] | None = None,
        self_state_block: str = "",
        self_query_meta: dict[str, Any] | None = None,
        role_scope: str = "owner",
    ) -> str:
        cfg = self._chat_layer_config()
        model = cfg.get("model", "")
        if not model:
            return "No chat layer model configured."
        incoming_text = str(text or "").strip()
        normalized_text = self._strip_oathweaver_vocative_prefix(incoming_text)
        text = normalized_text or incoming_text
        reply_target = dict(reply_to) if isinstance(reply_to, dict) else {}
        reply_target_content = str(
            reply_target.get("content", "") or reply_target.get("excerpt", "")
        ).strip()
        has_reply_target = bool(reply_target_content)
        project_slug = (project or self.project_slug or "").strip() or "general"
        if self._is_oathweaver_self_query(incoming_text):
            return self._oathweaver_identity_reply()
        if not self_state_block and not isinstance(self_query_meta, dict):
            try:
                self_state_block, self_query_meta = self._build_self_state_block(
                    incoming_text,
                    role_scope=role_scope,
                )
            except Exception:
                self_state_block, self_query_meta = "", {}
        if callable(cancel_checker):
            try:
                if bool(cancel_checker()):
                    return "Request cancelled before conversation generation started."
            except Exception:
                pass
        reminder_note = self._capture_daymarker_reminder(text)
        capture_rows = capture_history if isinstance(capture_history, list) else history
        event_note = self._capture_daymarker_event(text, history=capture_rows)
        if reminder_note and self._is_reminder_only_request(text):
            try:
                self.project_memory.ingest_text(project_slug, text)
            except Exception:
                pass
            return self._append_daymarker_note(reminder_note, event_note)
        if event_note and self._is_event_only_request(text):
            try:
                self.project_memory.ingest_text(project_slug, text)
            except Exception:
                pass
            return self._append_daymarker_note(event_note, reminder_note)

        # ── Lightweight social path: skip heavy context for short acknowledgments ──
        # Skip when topic_context is set — user is asking about their domain.
        if not topic_context.strip() and not has_reply_target and self._is_lightweight_social(text):
            prior_messages = history[-24:] if isinstance(history, list) else []
            _social_sys = (
                (persona_override or self._weaver_persona_block())
                + "\n\nThis is ordinary conversation. Reply naturally, keep it light, and don't over-explain."
            )
            try:
                reply = self.ollama.chat(
                    model=model,
                    system_prompt=_social_sys,
                    user_prompt=text,
                    prior_messages=prior_messages,
                    temperature=float(cfg.get("temperature", 0.8)),
                    num_ctx=int(cfg.get("num_ctx", 8192)),
                    think=False,
                    timeout=max(int(cfg.get("timeout_sec", 30)), 30),
                    retry_attempts=int(cfg.get("retry_attempts", 2)),
                    retry_backoff_sec=float(cfg.get("retry_backoff_sec", 0.8)),
                    fallback_models=cfg.get("fallback_models", []) if isinstance(cfg.get("fallback_models", []), list) else [],
                )
                return self._surface_polish_reply(reply or "")
            except Exception:
                return ""

        if not topic_context.strip() and not has_reply_target and self._is_casual_conversation_turn(text) and not self._is_recency_sensitive(text) and not self._is_evolving_topic(text):
            prior_messages = history[-24:] if isinstance(history, list) else []
            _casual_sys = (
                (persona_override or self._weaver_persona_block())
                + "\n\nThis is ordinary conversation, not a work handoff. "
                "Answer directly in a relaxed, natural voice. "
                "No tool-talk, no project-manager phrasing, and no unnecessary scaffolding."
            )
            try:
                reply = self.ollama.chat(
                    model=model,
                    system_prompt=_casual_sys,
                    user_prompt=text,
                    prior_messages=prior_messages,
                    temperature=float(cfg.get("temperature", 0.8)),
                    num_ctx=min(int(cfg.get("num_ctx", 8192)), 8192),
                    think=False,
                    timeout=max(int(cfg.get("timeout_sec", 30)), 30),
                    retry_attempts=int(cfg.get("retry_attempts", 2)),
                    retry_backoff_sec=float(cfg.get("retry_backoff_sec", 0.8)),
                    fallback_models=cfg.get("fallback_models", []) if isinstance(cfg.get("fallback_models", []), list) else [],
                )
                return self._surface_polish_reply(reply or "")
            except Exception:
                return ""

        prior_messages = history[-24:] if isinstance(history, list) else []
        web_note = ""
        web_context = ""
        web_topic_type = "general"
        try:
            mode_info = self.pipeline_store.get(project_slug)
            if isinstance(mode_info, dict):
                web_topic_type = str(mode_info.get("topic_type", "general")).strip().lower() or "general"
        except Exception:
            web_topic_type = "general"
        recency_sensitive = self._is_recency_sensitive(text)
        evolving_topic = self._is_evolving_topic(text)
        if not recency_sensitive and prior_messages:
            if self._is_recency_sensitive_from_history(prior_messages):
                recency_sensitive = True
        live_query_text = self._contextual_live_query(text, prior_messages)
        must_verify_live = self._requires_live_verification(live_query_text, web_topic_type)
        if must_verify_live:
            recency_sensitive = True
        # Basic chat must never auto-trigger live web research. We rely on
        # model freshness notes + [FORAGE] hints so the user can choose Dig Deeper.
        web_note = ""
        web_context = ""
        web_details: dict[str, Any] = {}
        if isinstance(details_sink, dict):
            details_sink["web_note"] = web_note
            details_sink["web_context"] = web_context
            details_sink["web_details"] = {}
        if callable(cancel_checker):
            try:
                if bool(cancel_checker()):
                    return "Request cancelled before conversation model execution started."
            except Exception:
                pass
        _context_analysis, household_context, context_guidance = self._context_bundle_for_query(
            text,
            household_chars=1100,
        )
        # ── user_prompt: inject web context with mode-appropriate framing ──
        reply_role = str(reply_target.get("role", "assistant")).strip().lower() or "assistant"
        reply_excerpt = self._clip_prompt_text(
            reply_target.get("content", "") or reply_target.get("excerpt", ""),
            2200,
        )
        if reply_excerpt:
            user_prompt_base = (
                f"[Replying to a previous {reply_role} message in this thread:]\n"
                f"\"{reply_excerpt}\"\n\n"
                "User's follow-up:\n"
                f"{text}"
            )
        else:
            user_prompt_base = text
        user_prompt = user_prompt_base
        if must_verify_live and web_context.strip():
            user_prompt = (
                f"{user_prompt_base}\n\n"
                "Live verification context:\n"
                f"{web_context.strip()}\n\n"
                "Use the live context above for all current facts. "
                "If a requested detail is missing, unclear, or conflicting in the live context, say you could not verify it. "
                "Do not fill gaps from memory, prior patterns, or likely trends."
            )
        elif evolving_topic and web_context.strip():
            # Mode B: Evolving Knowledge — blend training + web
            user_prompt = (
                f"{user_prompt_base}\n\n"
                "Supplementary web context for freshness check:\n"
                f"{web_context.strip()}\n\n"
                "Answer this question from your own knowledge first. Then review the web context above "
                "and correct, update, or add to your answer where the web data is more current. "
                "If the web context confirms your knowledge, say so briefly. "
                "If it contradicts or updates your knowledge, note what changed. "
                "Do not mechanically separate 'training' vs 'web' — write one natural, unified answer."
            )
        elif web_context.strip():
            # Mode A: Current Events — web replaces training
            user_prompt = (
                f"{user_prompt_base}\n\n"
                "Live web context (extract news events/stories from this, not website descriptions):\n"
                f"{web_context.strip()}\n\n"
                "Report actual events and headlines found above. If the scraped text is only site navigation "
                "or platform features with no news content, ignore it and answer from training knowledge."
            )
        elif evolving_topic:
            # Evolving topic but no web context arrived
            user_prompt = (
                f"{user_prompt_base}\n\n"
                "[System note: This topic evolves over time. Answer from training knowledge, clearly note your knowledge cutoff, "
                "and include a short freshness note that newer sources may change details. "
                "If confidence is limited, append one [FORAGE: \"...\"] hint so the UI can offer Dig Deeper.]"
            )
        elif must_verify_live:
            user_prompt = (
                f"{user_prompt_base}\n\n"
                "[System note: This request is likely recency-sensitive. Do not auto-browse. "
                "Answer from your current knowledge with a clear cutoff caveat and add a brief note that fresh sources may be needed. "
                "When appropriate, append one [FORAGE: \"...\"] hint so the UI can offer Dig Deeper.]"
            )
        elif recency_sensitive:
            user_prompt = (
                f"{user_prompt_base}\n\n"
                "[System note: Basic chat does not auto-retrieve live sources. "
                "You may share what you know from training data, but frame it as knowledge from your training period "
                "(e.g. 'as of early 2025...' or 'last I knew...'). "
                "NEVER call this information 'fictional' — it is real but may be outdated. "
                "Add one concise note that fresh sources may be needed.]"
            )
        # ── RECENCY / FRESHNESS rule injected into system prompt ──
        if must_verify_live and web_context.strip():
            _recency_rule = (
                "LIVE VERIFICATION RULE: This request depends on current facts. "
                "Use only the live web context for those facts. "
                "If a requested detail is not clearly supported by the live context, explicitly say you could not verify it. "
                "Do not infer, estimate, or guess from memory, trends, prior cards, likely schedules, or partial matches. "
                "When possible, cite the source URLs or domains that support the verified details."
            )
        elif recency_sensitive and web_context.strip():
            _recency_rule = (
                "RECENCY RULE: This question requires current information. "
                "You have live web context — cite specific source URLs from it for any current facts. "
                "Do not rely on training knowledge where the web context provides an answer. "
            )
        elif evolving_topic and web_context.strip():
            _recency_rule = (
                "KNOWLEDGE FRESHNESS RULE: This question touches a topic that evolves over time. "
                "You have supplementary web context to cross-check your knowledge. "
                "Lead with what you know from training, then seamlessly incorporate any updates or corrections "
                "from the web context. If the web confirms your answer, a brief note like 'confirmed as of [date]' "
                "is enough. If the web shows something has changed, explain the update naturally. "
                "Cite source URLs only when reporting a specific change or update from the web data. "
                "Do not split your answer into 'what I knew' vs 'what the web says' sections."
            )
        elif recency_sensitive:
            _recency_rule = (
                "RECENCY RULE: No live web source was captured for this query. "
                "You can share training-data knowledge but must frame it with a time reference like 'as of early 2025' or 'last I knew'. "
                "Never use the word 'fictional' to describe training-data content — it is real, just potentially stale. "
                "When sharing news stories, include 3 major stories plus 1 lighter wildcard (sports, culture, weather, domestic). "
                "For each story, add a brief freshness note in parentheses: e.g. '(breaking)', '(ongoing since Feb)', '(last month)' so the user knows how current it is. "
                "After your answer, offer in one short sentence to run a live forage/search for current information. "
                "Do NOT direct the user to any external website, news outlet, or app — not even by name. "
                "Your only two moves are: answer from training data with a date caveat, or offer to forage yourself."
            )
        elif evolving_topic:
            _recency_rule = (
                "KNOWLEDGE FRESHNESS RULE: This question touches a topic that evolves over time, "
                "but no web source was retrieved. Answer from training knowledge with a brief note about "
                "your training cutoff. Offer to run a live search to confirm the information is still current."
            )
        else:
            _recency_rule = ""
        rejected_tool = self._extract_rejected_tool(text)
        if rejected_tool:
            user_prompt = (
                f"{user_prompt}\n\n"
                f"[User preference: Do not suggest or route through '{rejected_tool}'. "
                "Complete the request directly.]"
            )
        _topic_ctx = ""
        try:
            _topic_ctx = self.topic_memory.get_context_for_query(text)
        except Exception:
            pass
        _library_ctx = ""
        try:
            _conv_mode = self.pipeline_store.get(project_slug) or {}
            _conv_domain = str(_conv_mode.get("topic_type", "")).strip().lower()
            _library_ctx = self.library_service.context_text(
                text,
                project_slug=project_slug,
                topic_id=str(_conv_mode.get("topic_id", "")).strip(),
                domain=_conv_domain,
                limit=5,
            )
        except Exception:
            pass
        _project_research_ctx = ""
        _project_research_raw_ctx = ""
        _reply_research_ctx = ""
        try:
            research_bundle = self._project_research_brief(
                project_slug,
                query=text,
                max_chars=1200,
            )
            _project_research_ctx = str(research_bundle.get("brief", "")).strip()
            raw_excerpts = research_bundle.get("raw_excerpts")
            if isinstance(raw_excerpts, list):
                raw_lines = [
                    f"- {str(item).strip()[:600]}"
                    for item in raw_excerpts
                    if str(item).strip()
                ][:2]
                if raw_lines:
                    _project_research_raw_ctx = (
                        f"Raw research excerpts for project {project_slug}:\n"
                        + "\n".join(raw_lines)
                    )
            _reply_research_ctx = self._reply_to_research_summary_context(
                reply_target,
                max_chars=4000,
            )
        except Exception:
            pass
        _project_make_ctx = ""
        try:
            _project_make_ctx = self._project_make_brief(
                project_slug,
                max_items=5,
                max_chars=900,
            )
        except Exception:
            pass
        _general_ctx = ""
        try:
            _pool_query = text
            if prior_messages:
                last_user = [m["content"] for m in prior_messages[-4:] if m.get("role") == "user"]
                if last_user:
                    _pool_query = f"{text} {' '.join(last_user[-2:])}"
            matches = self._infra.general_pool.query(_pool_query, n=4)
            if matches:
                _general_ctx = "Relevant context from previous conversations:\n" + "\n".join(f"- {m}" for m in matches)
        except Exception:
            pass
        # ── Tiered system prompt: core always, extended only for substantive turns ──
        _has_injected_context = bool(
            household_context.strip() or web_context.strip() or _recency_rule or _library_ctx.strip()
            or _project_research_ctx.strip() or _project_research_raw_ctx.strip() or _reply_research_ctx.strip() or _project_make_ctx.strip()
        )
        _is_short_query = len(text.split()) < 10

        _talk_core = (
            f"Active project: {project_slug}. "
            "This is a normal back-and-forth. Answer directly and keep the exchange conversational. "
            "Stay with the user instead of drifting into project-manager mode unless they actually ask for work, planning, or research. "
            "Use prior chat only when it genuinely helps. Do not force callbacks or pretend to remember specifics you do not have. "
            "Identify yourself as part of the Oathweaver weaver layer, never as a base model name like Qwen or DeepSeek. "
            "No canned disclaimers. No 'as an AI' framing. "
        )
        if _is_short_query and not _has_injected_context:
            # Compact prompt for short questions with no context — reduces token pressure
            _talk_sys = _talk_core
        else:
            _talk_sys = (
                _talk_core
                + "When relevant household context is provided, use it to quietly protect commitments, "
                "family logistics, and timing constraints when that improves the answer. "
                "When live web context is provided, use it to answer recency-sensitive questions. "
                "For news/current-events queries: extract and report actual news STORIES, EVENTS, and HEADLINES "
                "found in the snippets — do NOT describe website features, video library navigation, "
                "user account systems, subscription prompts, or how a news platform works. "
                "If the scraped content contains only site-navigation boilerplate and no actual news events, "
                "say so briefly and answer from training knowledge with an appropriate date caveat. "
                "Cite source domains or URLs when reporting specific events from the web context. "
                "If the user rejects a tool/platform, stop recommending it and complete the requested task directly. "
                "Never redirect the user to an external website, app, news outlet, or platform to find an answer — "
                "you are the assistant, not a search engine referral. Do not say 'go to X' or 'check Y' or 'visit Z'. "
                "If you cannot answer with training data, offer to forage/search yourself, then stop. "
                "If prior conversation messages established a training-data timeframe or date caveat, "
                "maintain that same framing consistently on follow-up questions — do not silently reset "
                "to a different knowledge state mid-conversation. "
                f"{_recency_rule}"
                "CRITICAL: Do NOT make up specific facts, names, dates, statistics, or details you are uncertain about. "
                "If you are not confident in an answer, say so directly instead of guessing. "
                "When the user's question involves facts you are uncertain about, specific people or organizations you may not know well, "
                "recent events, evolving topics, or any case where a web lookup would give a better answer — "
                "append exactly ONE tag on its own line at the very end of your reply: [FORAGE: \"concise search-ready seed question\"]. "
                "Use a single seed that best covers the core information need. Never emit more than one [FORAGE:] tag. "
                "Omit this tag only for casual conversation, opinions, hypotheticals, creative requests, and topics you are fully confident about. "
                "When the user explicitly states something they need to do, an appointment they have, "
                "or an item to buy, you may append structured action tags on their own line at the very "
                "end of your reply (after any [FORAGE] tag):\n"
                "  Task:     [ADD_TASK: \"clear title\" due=\"YYYY-MM-DD\"]  (due date only if clearly stated)\n"
                "  Event:    [ADD_EVENT: \"event title\" date=\"YYYY-MM-DD\" time=\"HH:MM\"]  (24h time; time optional)\n"
                "  Shopping: [ADD_SHOPPING: \"item name\"]\n"
                "  Routine: [ADD_ROUTINE: \"title\" schedule=\"weekly_day\" weekday=\"monday\" time=\"HH:MM\"]  "
                "(weekly_day for weekly; monthly_day_of_month for monthly; time optional; "
                "add until=\"YYYY-MM-DD\" only if an end date was stated)\n"
                "Rules: Only emit when the user explicitly stated the item/event/recurrence — never infer or suggest. "
                "Multiple tags allowed on separate lines. Omit all tags for general advice, hypotheticals, "
                "or when no concrete action was mentioned by the user. "
                "Use ADD_ROUTINE only when the user explicitly says something recurs on a schedule — never for one-time events."
            )
        if has_reply_target:
            _talk_sys = (
                f"{_talk_sys}\n\n"
                "Reply-target rule: The user is replying to a specific earlier message shown with their prompt. "
                "Address that exact message content first, even if it falls outside the recent history window."
            )
        # Build system prompt top-to-bottom: instructions first, time-sensitive context last.
        # This gives primacy attention to the persona/task definition and recency attention
        # to the watchtower research card context (which contains the most time-sensitive facts).
        _talk_guidance = ""
        try:
            _talk_guidance = self.learning_engine.guidance_for_lane("project", limit=5)
        except Exception:
            pass
        _stack_caps = ""
        try:
            from orchestrator.services.make_catalog import stack_summary as _stack_summary
            _stack_caps = str(_stack_summary() or "").strip()
        except Exception:
            _stack_caps = ""
        _briefing_ctx = self._watchtower_context_for_query()
        _sys_parts = [(persona_override or self._weaver_persona_block()) + "\n\n" + _talk_sys]
        if self_state_block.strip():
            _sys_parts.append(self_state_block.strip())
        if topic_context.strip():
            _sys_parts.append(topic_context.strip())
        if _reply_research_ctx:
            _sys_parts.append(_reply_research_ctx)
        if _stack_caps:
            _sys_parts.append(_stack_caps)
        if context_guidance:
            _sys_parts.append(context_guidance)
        if household_context:
            _sys_parts.append(household_context)
        if _topic_ctx:
            _sys_parts.append(_topic_ctx)
        if _project_research_ctx:
            _sys_parts.append(_project_research_ctx)
        if _project_research_raw_ctx:
            _sys_parts.append(_project_research_raw_ctx)
        if _project_make_ctx:
            _sys_parts.append(_project_make_ctx)
        if _library_ctx:
            _sys_parts.append(_library_ctx)
        if _general_ctx:
            _sys_parts.append(_general_ctx)
        if _talk_guidance:
            _sys_parts.append(_talk_guidance)
        if _briefing_ctx:
            _sys_parts.append(_briefing_ctx)
        _talk_sys = "\n\n".join(p for p in _sys_parts if p.strip())
        try:
            reply = self.ollama.chat(
                model=model,
                system_prompt=_talk_sys,
                user_prompt=user_prompt,
                prior_messages=prior_messages,
                temperature=float(cfg.get("temperature", 0.8)),
                num_ctx=int(cfg.get("num_ctx", 8192)),
                think=bool(cfg.get("think", False)),
                timeout=max(int(cfg.get("timeout_sec", 180)), 1200),
                retry_attempts=int(cfg.get("retry_attempts", 3)),
                retry_backoff_sec=float(cfg.get("retry_backoff_sec", 1.2)),
                fallback_models=cfg.get("fallback_models", []) if isinstance(cfg.get("fallback_models", []), list) else [],
            )
            reply = self._surface_polish_reply(reply)
            reply = self._dedup_forage_tags(reply)
            if callable(cancel_checker):
                try:
                    if bool(cancel_checker()):
                        return "Request cancelled."
                except Exception:
                    pass
            try:
                if len(str(reply or "").strip()) > 80:
                    self._infra.general_pool.save(text[:80], str(reply).strip()[:200])
            except Exception:
                pass
            try:
                self.project_memory.ingest_text(project_slug, text)
                self._maybe_auto_refresh_project_facts(prior_messages)
                context_feedback = self._context_feedback(
                    user_text=text,
                    reply_text=reply,
                    household_context=household_context,
                )
                self._run_continuous_improvement(
                    user_text=text,
                    lane="project",
                    reply_text=reply,
                    worker_result=None,
                    context_feedback=context_feedback,
                )
            except Exception:
                pass
            reply = self._apply_self_state_safety_net(reply, self_query_meta=self_query_meta)
            reply = self._append_daymarker_note(reply, web_note)
            reply = self._append_daymarker_note(reply, event_note)
            return self._append_daymarker_note(reply, reminder_note)
        except Exception as exc:
            fallback = f"Conversation model call failed: {exc}"
            fallback = self._append_daymarker_note(fallback, web_note)
            fallback = self._append_daymarker_note(fallback, event_note)
            return self._append_daymarker_note(fallback, reminder_note)

    def _orchestrator_finalize(self, user_text: str, lane: str, worker_result: dict, fallback: str, topic_type: str = "general") -> str:
        cfg = lane_model_config(self.repo_root, "orchestrator_reasoning")
        model = cfg.get("model", "")
        if not model:
            return fallback

        # Underground: force abliterated model — no filtered models in the pipeline.
        _tt = str(topic_type or "").strip().lower()
        fallback_models = cfg.get("fallback_models", []) if isinstance(cfg.get("fallback_models", []), list) else []
        if _tt == "underground":
            model = "huihui_ai/qwen3-abliterated:8b-Q4_K_M"
            fallback_models = ["huihui_ai/qwen3-abliterated:8b-Q4_K_M"]

        system_prompt = (
            "You are the internal Oathweaver orchestrator. "
            "You receive worker outputs and return a faithful execution summary for an upper messenger layer. "
            "No persona, no charm, no motivational language. "
            "Always include: what completed, where outputs were written, and next best action. "
            "Do not arbitrarily compress or shorten content; include all materially relevant details. "
            "IMPORTANT: Do not mention how web sources were obtained or who supplied them. "
            "If source grounding is needed, cite URLs/domains directly without provenance chatter."
        )
        compact_worker = self._compact_worker_result_for_prompt(worker_result)
        compact_worker_text = json.dumps(compact_worker, ensure_ascii=True, sort_keys=True)
        user_prompt = (
            f"User request:\n{self._clip_prompt_text(user_text, 2200)}\n\n"
            f"Route lane: {lane}\n\n"
            f"Worker result object:\n{compact_worker_text}\n\n"
            "Return plain text. Be complete and include all materially relevant findings."
        )
        try:
            return self.ollama.chat(
                model=model,
                system_prompt=system_prompt,
                user_prompt=user_prompt,
                temperature=float(cfg.get("temperature", 0.2)),
                num_ctx=int(cfg.get("num_ctx", 16384)),
                think=False,  # formatting task — extended reasoning adds latency with no benefit
                timeout=int(cfg.get("timeout_sec", 300)),
                retry_attempts=int(cfg.get("retry_attempts", 4)),
                retry_backoff_sec=float(cfg.get("retry_backoff_sec", 1.5)),
                fallback_models=fallback_models,
            )
        except Exception:
            return fallback

    def _make_summary_reply(self, *, lane: str, out: dict[str, Any], fallback: str) -> str:
        """Return a terse summary-with-link reply for finished Make lane artifacts."""
        from orchestrator.services.make_catalog import label_for_type, MAKE_CATALOG
        artifact_path = str(out.get("path", "") or out.get("summary_path", "")).strip()
        delivery_kind = str(out.get("delivery_kind", "") or out.get("type_id", "")).strip()
        label = label_for_type(delivery_kind) if delivery_kind else lane.replace("make_", "").replace("_", " ").title()
        words = int(out.get("word_count", 0)) or 0
        files = int(out.get("files_written", 0)) or 0
        app_name = str(out.get("app_name", "") or out.get("name", "")).strip()
        ok = bool(out.get("ok", True))

        lines: list[str] = []
        if not ok:
            return fallback

        if app_name:
            lines.append(f"**Built:** {app_name}")
        lines.append(f"**Type:** {label}")
        if words:
            lines.append(f"**Words:** {words:,}")
        if files and not words:
            lines.append(f"**Files written:** {files}")
        if artifact_path:
            rel = artifact_path
            try:
                from pathlib import Path
                rel = str(Path(artifact_path).relative_to(self.repo_root))
            except Exception:
                pass
            lines.append(f"**Location:** `{rel}`")

        summary_text = str(out.get("message", "")).strip()
        if not summary_text and delivery_kind:
            summary_text = f"{label} draft complete."
        if summary_text:
            lines.append(f"\n{summary_text}")

        if artifact_path:
            rel = artifact_path
            try:
                from pathlib import Path
                from urllib.parse import quote
                rel_path = Path(artifact_path).relative_to(self.repo_root)
                rel = str(rel_path)
                link_url = f"/api/files/read?path={quote(rel, safe='/._-')}"
                lines.append(f"\n[Open artifact]({link_url})")
            except Exception:
                pass

        return "\n".join(lines) if lines else fallback

    def _clip_prompt_text(self, value: Any, limit_chars: int) -> str:
        text = str(value or "").strip()
        limit = max(200, int(limit_chars))
        if len(text) <= limit:
            return text
        tail = len(text) - limit
        return f"{text[:limit].rstrip()}\n...[truncated {tail} chars]"

    def _compact_worker_result_for_prompt(self, worker_result: dict[str, Any] | None) -> dict[str, Any]:
        if not isinstance(worker_result, dict):
            return {}

        def _clean_scalar(raw: Any, max_chars: int = 260) -> Any:
            if isinstance(raw, str):
                return self._clip_prompt_text(raw, max_chars)
            if isinstance(raw, (int, float, bool)) or raw is None:
                return raw
            return self._clip_prompt_text(str(raw), max_chars)

        compact: dict[str, Any] = {}
        keep_scalar_keys = (
            "ok",
            "status",
            "message",
            "project",
            "lane",
            "analysis_profile",
            "topic_type",
            "source_count",
            "topic_canon_added",
            "topic_reviews_created",
            "canceled",
            "cancel_summary",
            "model",
            "workers",
            "agents_total",
            "web_context_used",
            "summary_postprocessed",
        )
        keep_path_keys = (
            "summary_path",
            "raw_path",
            "path",
            "spec_path",
            "impl_path",
            "py_path",
            "markdown_path",
            "source_path",
        )
        for key in keep_scalar_keys:
            if key in worker_result:
                compact[key] = _clean_scalar(worker_result.get(key))
        for key in keep_path_keys:
            value = str(worker_result.get(key, "")).strip()
            if value:
                compact[key] = self._clip_prompt_text(value, 280)

        if isinstance(worker_result.get("models_used"), list):
            compact["models_used"] = [
                self._clip_prompt_text(str(x), 80)
                for x in worker_result.get("models_used", [])[:6]
                if str(x).strip()
            ]
            compact["models_used_total"] = len(worker_result.get("models_used", []))

        reliability = worker_result.get("reliability")
        if isinstance(reliability, dict):
            compact["reliability"] = {
                "agents_total": int(reliability.get("agents_total", 0) or 0),
                "good": int(reliability.get("good", 0) or 0),
                "weak": int(reliability.get("weak", 0) or 0),
                "failed": int(reliability.get("failed", 0) or 0),
            }

        web_details = worker_result.get("web_details")
        if isinstance(web_details, dict):
            web_compact: dict[str, Any] = {}
            for key in (
                "requested",
                "mode",
                "source_count",
                "seed_count",
                "query_variants_count",
                "conflict_count",
                "crawl_pages",
                "crawl_failures",
                "crawl_gated_links",
                "source_path",
            ):
                if key in web_details:
                    web_compact[key] = _clean_scalar(web_details.get(key))
            sources = web_details.get("sources")
            if isinstance(sources, list):
                preview: list[dict[str, str]] = []
                for src in sources[:6]:
                    if not isinstance(src, dict):
                        continue
                    row = {
                        "title": self._clip_prompt_text(str(src.get("title", "")).strip(), 120),
                        "domain": self._clip_prompt_text(str(src.get("source_domain", "")).strip(), 80),
                        "url": self._clip_prompt_text(str(src.get("url", "")).strip(), 140),
                    }
                    if row["title"] or row["domain"] or row["url"]:
                        preview.append(row)
                if preview:
                    web_compact["sources_preview"] = preview
                web_compact["sources_total"] = len(sources)
            if web_compact:
                compact["web_details"] = web_compact
        return compact

    def _weaver_relay(
        self,
        *,
        user_text: str,
        lane: str,
        internal_reply: str,
        worker_result: dict[str, Any] | None = None,
        topic_type: str = "general",
    ) -> str:
        cfg = self._chat_layer_config()
        model = str(cfg.get("model", "")).strip()
        if not model:
            return internal_reply

        fallback_models = cfg.get("fallback_models", []) if isinstance(cfg.get("fallback_models", []), list) else []
        if str(topic_type or "").strip().lower() == "underground":
            model = "huihui_ai/qwen3-abliterated:8b-Q4_K_M"
            fallback_models = ["huihui_ai/qwen3-abliterated:8b-Q4_K_M"]

        system_prompt = (
            self._weaver_persona_block()
            + "\n\n"
            + "You are relaying internal Oathweaver work back to the user. "
            "Translate the internal summary into natural language in weaver layer's voice. "
            "Stay faithful to the internal summary and worker result. Do not invent outcomes, paths, or evidence. "
            "Do not claim you personally executed tools or worker jobs. "
            "If something failed or is partial, say so plainly. "
            "Prioritize clarity and completeness; be concise only when it does not omit important details. "
            "If a next action is obvious, mention it once without turning it into a lecture."
        )
        compact_worker = self._compact_worker_result_for_prompt(worker_result)
        compact_worker_text = json.dumps(compact_worker, ensure_ascii=True, sort_keys=True)
        user_prompt = (
            f"User request:\n{self._clip_prompt_text(user_text, 2200)}\n\n"
            f"Lane: {lane}\n\n"
            f"Internal orchestrator summary:\n{self._clip_prompt_text(str(internal_reply or '').strip(), 9000)}\n\n"
            f"Worker result object:\n{compact_worker_text}\n\n"
            "Return plain text only."
        )
        try:
            reply = self.ollama.chat(
                model=model,
                system_prompt=system_prompt,
                user_prompt=user_prompt,
                temperature=float(cfg.get("temperature", 0.8)),
                num_ctx=int(cfg.get("num_ctx", 16384)),
                think=bool(cfg.get("think", False)),
                timeout=int(cfg.get("timeout_sec", 240)),
                retry_attempts=int(cfg.get("retry_attempts", 3)),
                retry_backoff_sec=float(cfg.get("retry_backoff_sec", 1.2)),
                fallback_models=fallback_models,
            )
            return self._surface_polish_reply(reply)
        except Exception:
            return internal_reply

    def _postprocess_research_summary(self, *, question: str, worker_result: dict[str, Any], topic_type: str) -> None:
        summary_path = str(worker_result.get("summary_path", "")).strip()
        if not summary_path:
            return
        path = Path(summary_path)
        if not path.exists():
            return
        try:
            original = path.read_text(encoding="utf-8", errors="ignore")
        except Exception:
            return
        sources: list[dict[str, Any]] = []
        web_details = worker_result.get("web_details", {}) if isinstance(worker_result.get("web_details", {}), dict) else {}
        if isinstance(web_details.get("sources", []), list):
            sources = [dict(x) for x in web_details.get("sources", []) if isinstance(x, dict)]
        if not sources:
            try:
                logs = self.web_engine.recent_sources_for_project(self.project_slug, limit=1)
                if logs and isinstance(logs[0].get("sources", []), list):
                    sources = [dict(x) for x in logs[0].get("sources", []) if isinstance(x, dict)]
            except Exception:
                sources = []
        fact_card_md = render_fact_card_markdown(question, sources, topic_type=topic_type)
        composed = compose_research_summary(
            original,
            sources=sources,
            topic_type=topic_type,
            question=question,
            fact_card_md=fact_card_md,
        )
        if composed.strip() and composed.strip() != original.strip():
            try:
                path.write_text(composed, encoding="utf-8")
                worker_result["summary_postprocessed"] = True
            except Exception:
                pass
        # Topic memory extraction — runs after summary is written so the composed
        # text is available in worker_result for the extractor.
        try:
            model_cfg = lane_model_config(self.repo_root, "orchestrator_reasoning")
            topic_result = self.topic_memory.extract_and_merge_from_research(
                worker_result,
                ollama_client=self.ollama,
                model_cfg=model_cfg,
            )
            worker_result["topic_canon_added"] = int(topic_result.get("canon_added", 0))
            worker_result["topic_reviews_created"] = int(topic_result.get("reviews_created", 0))
        except Exception:
            pass

    def _light_research_flow(self, *, question: str, lane: str, topic_type: str, project_context: str, trace: PerfTrace | None = None) -> dict[str, Any]:
        if trace:
            trace.start("light_web_lookup")
        web_result = self.web_engine.run_query(
            project=self.project_slug,
            lane=lane,
            query=question,
            reason="Adaptive light research path",
            request_id="auto",
            note="light research",
            topic_type=topic_type,
        )
        if trace:
            trace.end("light_web_lookup")
        sources = [dict(x) for x in (web_result.get("sources") or []) if isinstance(x, dict)]
        fact_card_md = render_fact_card_markdown(question, sources, topic_type=topic_type)
        context_bits = [project_context.strip()] if project_context.strip() else []
        try:
            _lr_topic_ctx = self.topic_memory.get_context_for_query(question)
            if _lr_topic_ctx:
                context_bits.insert(0, _lr_topic_ctx)
        except Exception:
            pass
        try:
            _lr_library_ctx = self.library_service.context_text(
                question,
                project_slug=self.project_slug,
                limit=2,
            )
            if _lr_library_ctx:
                context_bits.append(_lr_library_ctx)
        except Exception:
            pass
        retrieved = self.embedding_memory.context_text(self.project_slug, question, limit=2)
        if retrieved:
            context_bits.append(retrieved)
        if web_result.get("source_path"):
            context_bits.append(f"Web cache file: {web_result.get('source_path')}")
        model_cfg = lane_model_config(self.repo_root, "orchestrator_reasoning")
        model = str(model_cfg.get("model", "")).strip()
        # Underground: force abliterated model — no filtered models in the pipeline.
        _lr_tt = str(topic_type or "").strip().lower()
        _lr_unrestricted = _lr_tt == "underground"
        if _lr_unrestricted:
            model = "huihui_ai/qwen3-abliterated:8b-Q4_K_M"
        _lr_guidance = ""
        try:
            _lr_guidance = self.learning_engine.guidance_for_lane("research", limit=5)
        except Exception:
            pass
        answer = ""
        if model and sources:
            snippets: list[str] = []
            for idx, row in enumerate(sources[:6], start=1):
                snippets.append(
                    "[{}] {} | {}\n{}".format(
                        idx,
                        row.get("title", ""),
                        row.get("source_domain", ""),
                        str(row.get("snippet", ""))[:380],
                    )
                )
            prompt = (
                "Answer the user using ONLY the source snippets and local context below. "
                "Do not discuss how sources were obtained. "
                "Tag each claim [E] (sourced), [I] (inferred), or [S] (speculative). "
                "End with 'Confidence: X/5 — [reason]'. "
                "Be concise and say when details are uncertain.\n\n"
                f"Question: {question}\n\n"
                + "Local context:\n"
                + ("\n\n".join(context_bits)[:2400])
                + "\n\nSource snippets:\n"
                + ("\n\n".join(snippets)[:4000])
            )
            try:
                if trace:
                    trace.start("light_synthesis")
                _lr_sys = (
                    "You are Oathweaver. Produce a fast, accurate, source-grounded answer. "
                    "Do not mention how sources were obtained or who supplied them. "
                    "Label every claim with its evidence type:\n"
                    "  [E] = empirical — cite the source domain or URL.\n"
                    "  [I] = inference — frame as 'this suggests...' or 'likely...'\n"
                    "  [S] = speculation — frame as 'one possibility is...' or 'it may be...'\n"
                    "Never mix evidence types without labeling. Never launder [I] or [S] into stated facts. "
                    "End your answer with a single line: 'Confidence: X/5 — [one-line reason]'"
                )
                if _lr_guidance:
                    _lr_sys = f"{_lr_sys}\n\n{_lr_guidance}"
                answer = self.ollama.chat(
                    model=model,
                    system_prompt=_lr_sys,
                    user_prompt=prompt,
                    temperature=0.1,
                    num_ctx=min(int(model_cfg.get("num_ctx", 8192)), 8192),
                    think=False,
                    timeout=min(int(model_cfg.get("timeout_sec", 120)), 120),
                    retry_attempts=2,
                    retry_backoff_sec=0.8,
                    fallback_models=["huihui_ai/qwen3-abliterated:8b-Q4_K_M"] if _lr_unrestricted else (
                        model_cfg.get("fallback_models", []) if isinstance(model_cfg.get("fallback_models", []), list) else []
                    ),
                )
            except Exception:
                answer = ""
            finally:
                if trace:
                    trace.end("light_synthesis")
        if not answer.strip():
            bullets: list[str] = []
            for row in sources[:4]:
                title = str(row.get("title", "")).strip() or str(row.get("url", "")).strip()
                snippet = str(row.get("snippet", "")).strip()
                dom = str(row.get("source_domain", "")).strip()
                bullets.append(f"- {title} ({dom})\n  {snippet[:220]}")
            answer = "# Research Synthesis\n\n## Event Overview\n\n" + ("\n".join(bullets) if bullets else "No strong sources found.")
        composed = compose_research_summary(answer, sources=sources, topic_type=topic_type, question=question, fact_card_md=fact_card_md)
        raw_name = self.web_engine.store.timestamped_name("light_research_raw")
        raw_path = self.web_engine.store.write_project_file(self.project_slug, "research_raw", raw_name, answer + "\n")
        summary_name = self.web_engine.store.timestamped_name("light_research_summary")
        summary_path = self.web_engine.store.write_project_file(self.project_slug, "research_summaries", summary_name, composed + "\n")
        return {
            "ok": True,
            "message": "Adaptive light research completed.",
            "summary_path": str(summary_path),
            "raw_path": str(raw_path),
            "web_details": web_result,
            "analysis_profile": "light_research",
            "source_count": len(sources),
        }

    def _apply_confidence_gate(self, reply: str, *, sources: list[dict[str, Any]], conflict_summary: dict[str, Any] | None = None) -> str:
        confidence = evaluate_answer_confidence(sources=sources, conflict_summary=conflict_summary or {}, question=reply[:240])
        if confidence.get("mode") != "low":
            return reply
        notes = confidence.get("notes") or []
        gate = "\n\nCaution: source confidence is limited. "
        if notes:
            gate += " ".join(str(n) for n in notes[:3])
        return reply + gate


    def _attach_reflection_cycle(
        self,
        *,
        user_text: str,
        lane: str,
        reply_text: str,
        worker_result: dict | None = None,
    ) -> str:
        try:
            cycle = self.reflection_engine.create_cycle(
                project=self.project_slug,
                lane=lane,
                user_request=self._clip_prompt_text(user_text, 2000),
                orchestrator_reply=self._clip_prompt_text(reply_text, 10000),
                worker_result=self._compact_worker_result_for_prompt(worker_result if isinstance(worker_result, dict) else None),
            )
        except Exception:
            return reply_text

        self.bus.emit(
            "orchestrator",
            "reflection_cycle_created",
            {"id": cycle.get("id", ""), "lane": lane, "project": self.project_slug},
        )
        question = str(cycle.get("question_for_user", "")).strip()
        cycle_id = str(cycle.get("id", "")).strip()
        if not question or not cycle_id:
            return reply_text

        return (
            f"{reply_text}\n\n"
            f"Self-reflection check ({cycle_id}): {question}\n"
            f"Respond with: /reflect-answer {cycle_id} <your answer>"
        )

    def _count_user_messages(self, history: list[dict[str, str]] | None) -> int:
        if not isinstance(history, list):
            return 0
        count = 0
        for row in history:
            if not isinstance(row, dict):
                continue
            role = str(row.get("role", "")).strip().lower()
            if role != "user":
                continue
            if str(row.get("content", "")).strip():
                count += 1
        return count

    def _maybe_auto_refresh_project_facts(self, history: list[dict[str, str]] | None) -> None:
        if not isinstance(history, list) or not history:
            return
        user_count = self._count_user_messages(history)
        facts_count = len(self.project_memory.get_facts(self.project_slug))
        facts_updated_at = self.project_memory.get_updated_at(self.project_slug)
        should_refresh, reason = self.improvement_engine.should_refresh_facts(
            project=self.project_slug,
            history_user_count=user_count,
            facts_count=facts_count,
            facts_updated_at=facts_updated_at,
        )
        if not should_refresh:
            return
        result = self.project_memory.refresh_from_history(self.project_slug, history, reset=False)
        self.improvement_engine.note_fact_refresh(
            project=self.project_slug,
            reason=reason,
            refresh_result=result,
        )
        self.bus.emit(
            "orchestrator",
            "continuous_improve_facts_refreshed",
            {
                "project": self.project_slug,
                "reason": reason,
                "scanned_user_messages": result.get("scanned_user_messages", 0),
                "updated_fields": result.get("updated_fields", 0),
                "facts_count": result.get("facts_count", 0),
            },
        )

    def _run_continuous_improvement(
        self,
        *,
        user_text: str,
        lane: str,
        reply_text: str,
        worker_result: dict[str, Any] | None,
        context_feedback: dict[str, Any] | None = None,
    ) -> None:
        evaluation = self.improvement_engine.evaluate_turn(
            user_text=user_text,
            assistant_text=reply_text,
            lane=lane,
            worker_result=worker_result,
            context_feedback=context_feedback,
        )
        quality = float(evaluation.get("score", 0.5))
        context_score = float(evaluation.get("context_score", 0.5))
        outcome = str(evaluation.get("outcome", "mixed"))
        notes = evaluation.get("notes", [])
        lane_key = lane.strip().lower()
        if lane_key not in self.learning_engine.VALID_LANES:
            lane_key = "project"

        direction = self.improvement_engine.decide_reinforcement_direction(quality)
        reinforced_lesson_id = ""
        if direction:
            candidates = self.learning_engine.list_lessons(lane=lane_key, limit=6)
            if not candidates and lane_key != "project":
                candidates = self.learning_engine.list_lessons(lane="project", limit=6)
            for row in candidates:
                lesson_id = str(row.get("id", "")).strip()
                if not lesson_id:
                    continue
                note = (
                    f"continuous_improvement auto-{direction} | lane={lane_key} | "
                    f"quality_score={quality:.2f}"
                )
                updated = self.learning_engine.reinforce(lesson_id, direction=direction, note=note)
                if updated:
                    reinforced_lesson_id = lesson_id
                    self.bus.emit(
                        "orchestrator",
                        "continuous_improve_reinforced",
                        {
                            "project": self.project_slug,
                            "lane": lane_key,
                            "direction": direction,
                            "lesson_id": lesson_id,
                            "quality_score": quality,
                        },
                    )
                    break

        self.improvement_engine.note_turn(
            project=self.project_slug,
            lane=lane_key,
            quality_score=quality,
            context_score=context_score,
            outcome=outcome,
            notes=notes if isinstance(notes, list) else [],
            reinforcement_direction=direction if reinforced_lesson_id else "",
            reinforcement_lesson_id=reinforced_lesson_id,
        )

        # When quality drops below the reflection threshold, auto-answer stale open
        # reflection cycles in the background so their lessons flow into the learning store.
        if self.improvement_engine.should_trigger_reflection(quality):
            try:
                import threading
                threading.Thread(
                    target=self.reflection_engine.auto_answer_stale_cycles,
                    kwargs={"max_age_hours": 12.0},
                    daemon=True,
                ).start()
            except Exception:
                pass

    def _normalize_worker_result(self, lane: str, data: dict[str, Any] | None) -> WorkerResult:
        return WorkerResult.from_legacy(lane, data)

    def _complete_turn(
        self,
        *,
        user_text: str,
        lane: str,
        reply_text: str,
        worker_result: dict[str, Any] | None = None,
        context_feedback: dict[str, Any] | None = None,
    ) -> str:
        checked_reply = reply_text
        final_reply = self._attach_reflection_cycle(
            user_text=user_text,
            lane=lane,
            reply_text=checked_reply,
            worker_result=worker_result,
        )
        try:
            self._enqueue_library_ingest_from_worker_result(worker_result)
        except Exception:
            pass
        try:
            self._run_continuous_improvement(
                user_text=user_text,
                lane=lane,
                reply_text=final_reply,
                worker_result=worker_result,
                context_feedback=context_feedback or self._context_feedback(user_text=user_text, reply_text=final_reply),
            )
        except Exception:
            pass
        return final_reply

    def _collect_worker_artifact_paths(self, worker_result: dict[str, Any] | None) -> list[Path]:
        if not isinstance(worker_result, dict):
            return []
        paths: list[Path] = []
        candidate_keys = (
            "path",
            "summary_path",
            "raw_path",
            "source_path",
            "spec_path",
            "impl_path",
            "py_path",
            "markdown_path",
        )
        web_details = worker_result.get("web_details")
        if isinstance(web_details, dict):
            source_path = str(web_details.get("source_path", "")).strip()
            if source_path:
                try:
                    paths.append(Path(source_path))
                except Exception:
                    pass
        for key in candidate_keys:
            raw = str(worker_result.get(key, "")).strip()
            if not raw:
                continue
            try:
                paths.append(Path(raw))
            except Exception:
                continue
        dedup: list[Path] = []
        seen: set[str] = set()
        for raw_path in paths:
            try:
                path = raw_path if raw_path.is_absolute() else (self.repo_root / raw_path)
                resolved = path.resolve()
            except Exception:
                continue
            try:
                resolved.relative_to(self.repo_root / "Projects")
            except ValueError:
                continue
            key = str(resolved)
            if key in seen:
                continue
            seen.add(key)
            dedup.append(resolved)
        return dedup

    def _library_source_kind_for_artifact(self, path: Path) -> str:
        low = str(path).replace("\\", "/").lower()
        if "/research_summaries/" in low:
            return "reference"
        if "/review/" in low:
            return "review"
        return "notes"

    def _enqueue_library_ingest_for_artifact(self, artifact_path: Path, *, project_slug: str, source_origin: str) -> None:
        path = Path(artifact_path)
        if not path.exists() or not path.is_file():
            return
        ext = path.suffix.lower()
        if not is_document_ext(ext):
            return
        low = str(path).replace("\\", "/").lower()
        if "/research_web_sources/" in low:
            return
        source_kind = self._library_source_kind_for_artifact(path)
        mime = mimetypes.guess_type(path.name)[0] or ("text/markdown" if ext == ".md" else "text/plain")

        def _worker() -> None:
            try:
                item = self.library_service.intake_file(
                    path,
                    source_name=path.name,
                    mime=mime,
                    source_kind=source_kind,
                    title="",
                    topic_id="",
                    project_slug=project_slug,
                    source_origin=source_origin,
                    conversation_id="",
                )
                item_id = str(item.get("id", "")).strip()
                if item_id:
                    self.library_service.enqueue_ingest(item_id)
            except Exception:
                pass

        threading.Thread(
            target=_worker,
            daemon=True,
            name=f"oathweaver-library-artifact-{uuid.uuid4().hex[:8]}",
        ).start()

    def _enqueue_library_ingest_from_worker_result(self, worker_result: dict[str, Any] | None) -> None:
        paths = self._collect_worker_artifact_paths(worker_result)
        if not paths:
            return
        project_slug = str((worker_result or {}).get("project", "")).strip() or str(self.project_slug).strip() or "general"
        for path in paths:
            self._enqueue_library_ingest_for_artifact(
                path,
                project_slug=project_slug,
                source_origin="project_artifact",
            )

    def _should_offer_web(self, text: str, lane: str) -> bool:
        return should_offer_web(text, lane)

    def _routing_context_gate(
        self,
        text: str,
        prior_messages: list[dict[str, str]],
        *,
        trigger_reason: str = "keyword",
        timeout: int = 12,
    ) -> bool:
        """Consolidated policy entrypoint: True allows web fetch, False suppresses."""
        return should_route_web_fetch(
            text,
            prior_messages,
            repo_root=self.repo_root,
            trigger_reason=trigger_reason,
        )

    def _is_recency_sensitive_from_history(self, prior_messages: list, lookback: int = 4) -> bool:
        return is_recency_sensitive_from_history(prior_messages, lookback)

    def _is_recency_sensitive(self, text: str) -> bool:
        return is_recency_sensitive(text)

    def _is_evolving_topic(self, text: str) -> bool:
        return is_evolving_topic(text)

    def _requires_live_verification(self, text: str, topic_type: str = "general") -> bool:
        raw = str(text or "").strip()
        if not raw:
            return False
        low = raw.lower()
        if self._is_recency_sensitive(raw):
            return True
        resolved_type = detect_topic_type(raw, topic_type)
        volatility = classify_fact_volatility(raw, topic_type, raw)
        if resolved_type in {"combat_sports", "sports_event"}:
            if any(marker in low for marker in _LIVE_VERIFICATION_MARKERS):
                return True
            if any(token in low for token in {"card", "bout", "matchup", "opponent", "fight", "vs", "versus"}):
                return True
        if volatility == "volatile":
            return bool(self._is_recency_sensitive(raw) or resolved_type in {"current_events", "combat_sports", "sports_event"})
        return False

    @staticmethod
    def _contextual_live_query(text: str, prior_messages: list[dict[str, str]] | None = None) -> str:
        base = str(text or "").strip()
        rows = prior_messages if isinstance(prior_messages, list) else []
        if not base or not rows:
            return base
        recent_users: list[str] = []
        for row in rows[-8:]:
            if str(row.get("role", "")).strip().lower() != "user":
                continue
            content = str(row.get("content", "")).strip()
            if content:
                recent_users.append(content)
        if not recent_users:
            return base
        if len(base.split()) >= 12:
            return base
        combined = " ".join(recent_users[-2:] + [base]).strip()
        return combined[:500]

    def _extract_rejected_tool(self, text: str) -> str:
        return extract_rejected_tool(text)

    def _web_learning_feedback(self, query: str, sources: list[dict[str, Any]]) -> str:
        lines = [f"Web source cache for query: {query}", "Top sources captured:"]
        for row in sources[:6]:
            title = str(row.get("title", "")).strip()
            url = str(row.get("url", "")).strip()
            if not url:
                continue
            tier = str(row.get("source_tier", "tier3")).strip() or "tier3"
            score = float(row.get("source_score", 0.0))
            lines.append(f"- [{tier} {score:.2f}] {title or url}: {url}")
            snippet = str(row.get("snippet", "")).strip()
            if snippet:
                lines.append(f"  snippet: {snippet[:240]}")
        return "\n".join(lines)

    def _cloud_learning_feedback(self, *, query: str, provider: str, model: str, response_text: str) -> str:
        lines = [
            f"Cloud consult for query: {query}",
            f"Provider: {provider}",
            f"Model: {model}",
            "Response excerpt:",
            response_text.strip()[:2000],
        ]
        return "\n".join(lines)

    def _read_file_preview(self, path_text: str, limit: int = 8000) -> str:
        raw = path_text.strip()
        if not raw:
            return ""
        path = Path(raw)
        if not path.is_absolute():
            path = self.repo_root / path
        try:
            resolved = path.resolve(strict=True)
        except OSError:
            return ""
        try:
            resolved.relative_to(self.repo_root)
        except ValueError:
            return ""
        try:
            body = resolved.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            body = resolved.read_text(encoding="utf-8-sig")
        except OSError:
            return ""
        return body[: max(500, min(limit, 30000))]

    def _prepare_web_context(self, *, text: str, lane: str, topic_type: str = "general", force: bool = False, quick: bool = False, progress_callback=None) -> tuple[str, str, dict[str, Any]]:
        mode = self.web_engine.get_mode()
        lane_key = lane.strip().lower()
        normalized_topic_type = str(topic_type or "").strip().lower() or "general"
        details: dict[str, Any] = {
            "mode": mode,
            "requested": False,
            "pending_id": "",
            "source_path": "",
            "source_count": 0,
            "seed_count": 0,
            "query_expansion_enabled": False,
            "query_variants_count": 0,
            "query_variants": [],
            "variant_hits": [],
            "source_scoring_enabled": False,
            "source_scoring_summary": {},
            "conflict_detection_enabled": False,
            "conflict_summary": {},
            "conflict_count": 0,
            "crawl_relevance_gating_enabled": False,
            "crawl_gated_links": 0,
            "crawl_pages": 0,
            "crawl_failures": 0,
            "sources": [],
        }
        if mode == "off":
            return "", "", details
        if not force and not self._should_offer_web(text, lane_key):
            return "", "", details

        reason = "Live web refresh for source citations and recency checks."
        run_tag = "AUTO" if mode == "auto" else "ASK"

        runner = self.web_engine.run_quick_query if quick else self.web_engine.run_query
        result = runner(
            project=self.project_slug,
            lane=lane_key,
            query=text,
            reason=reason,
            request_id="auto" if mode == "auto" else "ask_auto_try",
            note=("quick chat web mode" if quick else "auto web mode") if mode == "auto" else ("quick ask mode auto-try" if quick else "ask mode auto-try"),
            topic_type=normalized_topic_type,
            progress_callback=progress_callback,
        )
        details["requested"] = True
        details["source_path"] = str(result.get("source_path", ""))
        details["source_count"] = int(result.get("source_count", 0))
        details["seed_count"] = int(result.get("seed_count", 0))
        details["query_expansion_enabled"] = bool(result.get("query_expansion_enabled", False))
        details["query_variants_count"] = int(result.get("query_variants_count", 0))
        details["query_variants"] = result.get("query_variants", []) if isinstance(result.get("query_variants", []), list) else []
        details["variant_hits"] = result.get("variant_hits", []) if isinstance(result.get("variant_hits", []), list) else []
        details["source_scoring_enabled"] = bool(result.get("source_scoring_enabled", False))
        details["source_scoring_summary"] = result.get("source_scoring_summary", {}) if isinstance(result.get("source_scoring_summary", {}), dict) else {}
        details["conflict_detection_enabled"] = bool(result.get("conflict_detection_enabled", False))
        details["conflict_summary"] = result.get("conflict_summary", {}) if isinstance(result.get("conflict_summary", {}), dict) else {}
        details["conflict_count"] = int(details["conflict_summary"].get("conflict_count", 0))
        details["crawl_relevance_gating_enabled"] = bool(result.get("crawl_relevance_gating_enabled", False))
        details["crawl_gated_links"] = int(result.get("crawl_gated_links", 0))
        details["crawl_pages"] = int(result.get("crawl_pages", 0))
        details["crawl_failures"] = int(result.get("crawl_failures", 0))
        details["sources"] = result.get("sources", []) if isinstance(result.get("sources", []), list) else []
        details["intel_summary"] = result.get("intel_summary", {}) if isinstance(result.get("intel_summary", {}), dict) else {}
        details["cache_hit"] = bool(result.get("cache_hit", False))
        details["cache_disclosure"] = str(result.get("cache_disclosure", "")).strip()
        if bool(result.get("ok", False)):
            feedback_text = self._web_learning_feedback(text, result.get("sources", []))
            self.learning_engine.ingest_feedback_text(
                feedback_text=feedback_text,
                source="web_cache",
                lane_hint="research",
                project=self.project_slug,
                source_file=str(result.get("source_path", "web:auto")),
                origin_type=ORIGIN_REFLECTION,
            )
            try:
                _rep = DomainReputation(self.repo_root)
                for _src in result.get("sources", []):
                    _domain = str(_src.get("source_domain", "") or _src.get("domain", "")).strip()
                    if _domain:
                        _rep.record_success(_domain)
            except Exception:
                pass
            self.bus.emit(
                "orchestrator",
                "web_research_auto_completed",
                {
                    "project": self.project_slug,
                    "lane": lane_key,
                    "mode": mode,
                    "source_count": details["source_count"],
                    "seed_count": details["seed_count"],
                    "query_expansion_enabled": details["query_expansion_enabled"],
                    "query_variants_count": details["query_variants_count"],
                    "source_scoring_enabled": details["source_scoring_enabled"],
                    "conflict_count": details["conflict_count"],
                    "crawl_pages": details["crawl_pages"],
                    "crawl_failures": details["crawl_failures"],
                    "crawl_gated_links": details["crawl_gated_links"],
                    "source_path": details["source_path"],
                },
            )
            fresh_context = self.web_engine.web_context_for_project(self.project_slug, limit=8)
            cache_note = details["cache_disclosure"] if details.get("cache_hit") and details.get("cache_disclosure") else ""
            return cache_note, fresh_context, details

        message = str(result.get("message", "")).strip() or "No web sources found."
        if mode == "ask":
            pending = self.web_engine.create_pending(
                project=self.project_slug,
                lane=lane_key,
                query=text,
                reason=f"{reason} Automatic run in ASK mode failed and needs user/codex decision.",
                topic_type=normalized_topic_type,
            )
            details["pending_id"] = str(pending.get("id", ""))
            self.bus.emit(
                "orchestrator",
                "web_research_pending",
                {"id": details["pending_id"], "project": self.project_slug, "lane": lane_key, "mode": mode},
            )
            note = (
                "Web ASK mode could not capture live sources.\n"
                f"Pending action created: {details['pending_id']}.\n"
                "Use Pending Actions: Answer directly, Ignore, or Move to Codex inbox."
            )
            return note, "", details

        self.learning_engine.ingest_feedback_text(
            feedback_text=(
                "Web research auto-run failed to produce sources.\n"
                f"Query: {text}\n"
                f"Lane: {lane_key}\n"
                f"Failure: {message}\n"
                "Policy: continue local pipeline without creating blocking pending actions."
            ),
            source="web_research_nonblocking_fail",
            lane_hint=lane_key,
            project=self.project_slug,
            source_file="web:auto_nonblocking",
            origin_type=ORIGIN_REFLECTION,
        )
        self.bus.emit(
            "orchestrator",
            "web_research_nonblocking_failed",
            {"project": self.project_slug, "lane": lane_key, "mode": mode, "message": message},
        )
        note = (
            f"Web {run_tag} mode could not capture live sources; continued without blocking.\n"
            "I logged the failure pattern for learning and kept progress moving."
        )
        return note, "", details

    def _extract_reminder_from_text(self, text: str) -> dict[str, str] | None:
        return _extract_reminder(text)

    def _household_source_for_context(self) -> None:
        return None

    def _household_context_for_query(self, text: str, max_chars: int = 1200) -> str:
        return ""

    def _watchtower_context_for_query(self, max_chars: int = 600) -> str:
        try:
            return self.watchtower.recent_research_card_context(limit=2, max_chars=max_chars)
        except Exception:
            return ""

    @staticmethod
    def _personal_context_detected(analysis: dict[str, Any]) -> bool:
        if not isinstance(analysis, dict):
            return False
        return any(
            bool(analysis.get(flag, False))
            for flag in (
                "explicit_memory_query",
                "family_query",
                "pet_query",
                "profile_query",
                "preference_query",
                "routine_query",
            )
        )

    def _context_bundle_for_query(
        self,
        text: str,
        *,
        household_chars: int = 1200,
    ) -> tuple[dict[str, Any], str, str]:
        analysis = analyze_query_context(text)
        household_context = ""
        guidance = build_context_usage_guidance(
            analysis,
            personal_available=False,
        )
        return analysis, household_context, guidance

    def _context_feedback(
        self,
        *,
        user_text: str,
        reply_text: str,
        household_context: str = "",
    ) -> dict[str, Any]:
        return evaluate_context_use(
            user_text,
            reply_text,
            personal_context_available=False,
            personal_context_injected=False,
        )

    def _capture_daymarker_reminder(self, text: str) -> str:
        return ""

    def _capture_daymarker_event(self, text: str, history: list[dict[str, str]] | None = None) -> str:
        return ""

    def _latest_research_summary_preview(self, project_slug: str, limit_chars: int = 7000) -> tuple[str, str]:
        return _latest_research_preview(self.repo_root, project_slug, limit_chars=limit_chars)

    def _read_research_context(self, project_slug: str, max_summaries: int = 3, chars_per_summary: int = 6000) -> str:
        return _read_research_ctx(self.repo_root, project_slug, max_summaries=max_summaries, chars_per_summary=chars_per_summary)

    def _read_raw_notes_context(self, project_slug: str, max_files: int = 2, chars_per_file: int = 4000) -> str:
        return _read_raw_notes_ctx(self.repo_root, project_slug, max_files=max_files, chars_per_file=chars_per_file)

    def _read_sources_context(self, project_slug: str, limit: int = 14) -> str:
        return _read_sources_ctx(self.web_engine, project_slug, limit=limit)

    def _infer_delivery_target(self, text: str, explicit_target: str, mode: str = "research") -> str:
        return infer_delivery_target(text, explicit_target, mode)

    def _run_make_plan(
        self,
        *,
        text: str,
        target: str,
        mode: str = "make",
        upstream_requirements: dict[str, Any] | None = None,
        upstream_architecture: dict[str, Any] | None = None,
        upstream_implementation_plan: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        current_mode = str(mode or "make").strip().lower()
        kind = self._infer_delivery_target(text, target, mode=current_mode)
        requirements = dict(upstream_requirements or {})
        architecture = dict(upstream_architecture or {})
        implementation = dict(upstream_implementation_plan or {})

        extracted_entities = requirements.get("extracted_entities", []) if isinstance(requirements, dict) else []
        extracted_actions = requirements.get("extracted_actions", []) if isinstance(requirements, dict) else []
        extracted_constraints = requirements.get("extracted_constraints", []) if isinstance(requirements, dict) else []
        module_breakdown = architecture.get("module_breakdown", []) if isinstance(architecture, dict) else []
        ordered_steps = implementation.get("ordered_steps", []) if isinstance(implementation, dict) else []
        deliverable_files = implementation.get("deliverable_files", []) if isinstance(implementation, dict) else []

        stamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        safe_kind = re.sub(r"[^a-z0-9_]+", "_", str(kind or "plan").strip().lower()).strip("_") or "plan"
        out_root = self.repo_root / "Projects" / "Plans" / self.project_slug
        out_root.mkdir(parents=True, exist_ok=True)
        out_path = out_root / f"{stamp}_{safe_kind}_plan.md"

        lines: list[str] = [
            f"# Implementation Plan: {safe_kind.replace('_', ' ').title()}",
            "",
            "## Request",
            text.strip(),
            "",
            "## Requirements",
        ]
        if extracted_entities:
            lines.append("### Entities")
            lines.extend([f"- {str(item).strip()}" for item in extracted_entities if str(item).strip()])
            lines.append("")
        if extracted_actions:
            lines.append("### Actions")
            lines.extend([f"- {str(item).strip()}" for item in extracted_actions if str(item).strip()])
            lines.append("")
        if extracted_constraints:
            lines.append("### Constraints")
            lines.extend([f"- {str(item).strip()}" for item in extracted_constraints if str(item).strip()])
            lines.append("")
        if not extracted_entities and not extracted_actions and not extracted_constraints:
            lines.append("- (No structured requirements extracted.)")
            lines.append("")

        lines.append("## Architecture")
        stack_summary = str(architecture.get("stack_summary", "")).strip() if isinstance(architecture, dict) else ""
        if stack_summary:
            lines.append(stack_summary)
            lines.append("")
        modules = module_breakdown if isinstance(module_breakdown, list) else []
        if modules:
            for module in modules:
                if not isinstance(module, dict):
                    continue
                name = str(module.get("name", "")).strip()
                responsibility = str(module.get("responsibility", "")).strip()
                if name and responsibility:
                    lines.append(f"- **{name}:** {responsibility}")
                elif name:
                    lines.append(f"- **{name}**")
            lines.append("")
        else:
            lines.append("- (No module breakdown extracted.)")
            lines.append("")

        lines.append("## Implementation Steps")
        if ordered_steps:
            for idx, step in enumerate(ordered_steps, start=1):
                step_text = str(step).strip()
                if step_text:
                    lines.append(f"{idx}. {step_text}")
            lines.append("")
        else:
            lines.append("1. (No ordered implementation steps extracted.)")
            lines.append("")

        lines.append("## Candidate Files")
        if deliverable_files:
            lines.extend([f"- `{str(path).strip()}`" for path in deliverable_files if str(path).strip()])
        else:
            lines.append("- (No file suggestions extracted.)")
        lines.append("")

        out_path.write_text("\n".join(lines).strip() + "\n", encoding="utf-8")
        self.bus.emit(
            "orchestrator",
            "make_deliverable_written",
            {"project": self.project_slug, "kind": "plan", "path": str(out_path), "delivery_kind": "plan"},
        )
        return {
            "ok": True,
            "message": "Plan generated. Review steps before code execution.",
            "path": str(out_path),
            "delivery_kind": "plan",
            "type_id": safe_kind,
            "requirements": {
                "entities": [str(x).strip() for x in extracted_entities if str(x).strip()],
                "actions": [str(x).strip() for x in extracted_actions if str(x).strip()],
                "constraints": [str(x).strip() for x in extracted_constraints if str(x).strip()],
            },
            "architecture": architecture,
            "implementation_plan": implementation,
        }

    def _run_make_delivery(
        self,
        *,
        text: str,
        history: list[dict[str, str]] | None,
        target: str,
        mode: str = "research",
        seed_artifact_text: str = "",
        upstream_requirements: dict[str, Any] | None = None,
        upstream_architecture: dict[str, Any] | None = None,
        upstream_implementation_plan: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        current_mode = str(mode or "research").strip().lower()
        kind = self._infer_delivery_target(text, target, mode=current_mode)
        if kind in {"web_app", "standalone_app", "app", "dashboard", "landing_page", "api"}:
            research_context = self._merge_make_seed_context(
                self._read_research_context(self.project_slug, max_summaries=2, chars_per_summary=4000),
                seed_artifact_text,
            )
            out = self._run_registered_agent(
                "make_app",
                self._make_agent_task(
                    lane="make_app",
                    text=text,
                    context={
                        "research_context": research_context,
                        "upstream_requirements": dict(upstream_requirements or {}),
                        "upstream_architecture": dict(upstream_architecture or {}),
                        "upstream_implementation_plan": dict(upstream_implementation_plan or {}),
                    },
                    cancel_checker=getattr(self, "_last_cancel_checker", None),
                    progress_callback=getattr(self, "_last_progress_callback", None),
                ),
            )
            out["delivery_kind"] = kind
            self.bus.emit(
                "orchestrator",
                "make_deliverable_written",
                {"project": self.project_slug, "kind": kind, "path": out.get("path", "")},
            )
            return out

        # --- Essay / Report / Brief / Document: multi-pass pipeline ---
        if kind in {"essay", "brief", "report", "document"}:
            research_context = self._merge_make_seed_context(
                self._read_research_context(self.project_slug),
                seed_artifact_text,
            )
            raw_notes_context = self._read_raw_notes_context(self.project_slug)
            sources_context = self._read_sources_context(self.project_slug)
            # Resolve topic_type from project_mode if available
            _pm = getattr(self, "_last_project_mode", {})
            topic_type = str(_pm.get("topic_type", "general")).strip().lower() if isinstance(_pm, dict) else "general"
            essay_result = self._run_registered_agent(
                "make_doc",
                self._make_agent_task(
                    lane="make_doc",
                    text=text,
                    context={
                        "topic_type": topic_type,
                        "target": kind,
                        "research_context": research_context,
                        "raw_notes_context": raw_notes_context,
                        "sources_context": sources_context,
                    },
                    progress_callback=getattr(self, "_last_progress_callback", None),
                ),
            )
            essay_body = str(essay_result.get("body", "")).strip()
            if not essay_body:
                essay_body = f"# {kind.title()} Draft\n\n(Essay pool returned no content.)\n"
            stamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
            deliverable_root = self.repo_root / "Projects" / "Essays-Scripts" / self.project_slug
            deliverable_root.mkdir(parents=True, exist_ok=True)
            out_path = deliverable_root / f"{stamp}_{kind}.md"
            out_path.write_text(essay_body + "\n", encoding="utf-8")
            self.bus.emit(
                "orchestrator",
                "make_deliverable_written",
                {"project": self.project_slug, "kind": kind, "path": str(out_path)},
            )
            return {
                "ok": essay_result.get("ok", True),
                "message": essay_result.get("message", f"MAKE lane drafted a {kind}."),
                "path": str(out_path),
                "delivery_kind": kind,
                "sections_written": essay_result.get("sections_written", []),
            }

        # --- Creative writing: novel, memoir, book, screenplay ---
        if kind in {"novel", "memoir", "book", "screenplay"}:
            research_context = self._merge_make_seed_context(
                self._read_research_context(self.project_slug),
                seed_artifact_text,
            )
            _pm_creative = getattr(self, "_last_project_mode", {})
            topic_type_creative = str(_pm_creative.get("topic_type", "general")).strip().lower() if isinstance(_pm_creative, dict) else "general"
            creative_result = self._run_registered_agent(
                "make_creative",
                self._make_agent_task(
                    lane="make_creative",
                    text=text,
                    context={
                        "target": kind,
                        "topic_type": topic_type_creative,
                        "research_context": research_context,
                    },
                    cancel_checker=getattr(self, "_last_cancel_checker", None),
                    progress_callback=getattr(self, "_last_progress_callback", None),
                ),
            )
            creative_body = str(creative_result.get("body", "")).strip()
            if not creative_body:
                creative_body = f"# {kind.title()} Draft\n\n(Creative pool returned no content.)\n"
            stamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
            deliverable_root = self.repo_root / "Projects" / "Creative" / self.project_slug
            deliverable_root.mkdir(parents=True, exist_ok=True)
            out_path = deliverable_root / f"{stamp}_{kind}.md"
            out_path.write_text(creative_body + "\n", encoding="utf-8")
            self.bus.emit(
                "orchestrator",
                "make_deliverable_written",
                {"project": self.project_slug, "kind": kind, "path": str(out_path)},
            )
            return {
                "ok": creative_result.get("ok", True),
                "message": creative_result.get("message", f"MAKE lane drafted a {kind}."),
                "path": str(out_path),
                "delivery_kind": kind,
                "scenes_written": creative_result.get("scenes_written", []),
            }

        # --- Short-form content: blog, social_post, email ---
        if kind in {"blog", "social_post", "email"}:
            research_context = self._merge_make_seed_context(
                self._read_research_context(self.project_slug, max_summaries=2, chars_per_summary=4000),
                seed_artifact_text,
            )
            raw_notes_context_content = self._read_raw_notes_context(self.project_slug)
            _pm_content = getattr(self, "_last_project_mode", {})
            topic_type_content = str(_pm_content.get("topic_type", "general")).strip().lower() if isinstance(_pm_content, dict) else "general"
            content_result = self._run_registered_agent(
                "make_content",
                self._make_agent_task(
                    lane="make_content",
                    text=text,
                    context={
                        "target": kind,
                        "topic_type": topic_type_content,
                        "research_context": research_context,
                        "raw_notes_context": raw_notes_context_content,
                    },
                    cancel_checker=getattr(self, "_last_cancel_checker", None),
                    progress_callback=getattr(self, "_last_progress_callback", None),
                ),
            )
            content_body = str(content_result.get("body", "")).strip()
            if not content_body:
                content_body = f"# {kind.replace('_', ' ').title()} Draft\n\n(Content pool returned no content.)\n"
            stamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
            deliverable_root = self.repo_root / "Projects" / "Content" / self.project_slug
            deliverable_root.mkdir(parents=True, exist_ok=True)
            out_path = deliverable_root / f"{stamp}_{kind}.md"
            out_path.write_text(content_body + "\n", encoding="utf-8")
            self.bus.emit(
                "orchestrator",
                "make_deliverable_written",
                {"project": self.project_slug, "kind": kind, "path": str(out_path)},
            )
            return {
                "ok": content_result.get("ok", True),
                "message": content_result.get("message", f"MAKE lane drafted a {kind.replace('_', ' ')}."),
                "path": str(out_path),
                "delivery_kind": kind,
            }

        # --- Domain specialist: medical, finance, sports, history, game_design_doc ---
        if kind in {"medical", "finance", "sports", "history", "game_design_doc"}:
            research_context = self._merge_make_seed_context(
                self._read_research_context(self.project_slug),
                seed_artifact_text,
            )
            raw_notes_context = self._read_raw_notes_context(self.project_slug)
            sources_context = self._read_sources_context(self.project_slug)
            _pm = getattr(self, "_last_project_mode", {})
            topic_type = str(_pm.get("topic_type", "general")).strip().lower() if isinstance(_pm, dict) else "general"
            specialist_result = self._run_registered_agent(
                "make_specialist",
                self._make_agent_task(
                    lane="make_specialist",
                    text=text,
                    context={
                        "topic_type": topic_type,
                        "target": kind,
                        "research_context": research_context,
                        "raw_notes_context": raw_notes_context,
                        "sources_context": sources_context,
                    },
                    cancel_checker=getattr(self, "_last_cancel_checker", None),
                    progress_callback=getattr(self, "_last_progress_callback", None),
                ),
            )
            specialist_body = str(specialist_result.get("body", "")).strip()
            if not specialist_body:
                specialist_body = f"# {kind.replace('_', ' ').title()} Draft\n\n(Specialist pool returned no content.)\n"
            stamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
            _SPECIALIST_DIRS = {
                "medical": "Medical", "finance": "Finance", "sports": "Sports",
                "history": "History", "game_design_doc": "GameDesign",
            }
            dir_name = _SPECIALIST_DIRS.get(kind, "Specialist")
            deliverable_root = self.repo_root / "Projects" / dir_name / self.project_slug
            deliverable_root.mkdir(parents=True, exist_ok=True)
            out_path = deliverable_root / f"{stamp}_{kind}.md"
            out_path.write_text(specialist_body + "\n", encoding="utf-8")
            self.bus.emit(
                "orchestrator",
                "make_deliverable_written",
                {"project": self.project_slug, "kind": kind, "path": str(out_path)},
            )
            return {
                "ok": specialist_result.get("ok", True),
                "message": specialist_result.get("message", f"MAKE lane drafted a {kind.replace('_', ' ')}."),
                "path": str(out_path),
                "delivery_kind": kind,
                "sections_written": specialist_result.get("sections_written", []),
            }

        # --- Longform writing: essay_long, essay_short, guide, tutorial, video_script, newsletter, press_release ---
        _LONGFORM_KINDS = {"essay_long", "essay_short", "guide", "tutorial", "video_script", "newsletter", "press_release"}
        if kind in _LONGFORM_KINDS:
            research_context = self._merge_make_seed_context(
                self._read_research_context(self.project_slug, max_summaries=2, chars_per_summary=4000),
                seed_artifact_text,
            )
            raw_notes_context = self._read_raw_notes_context(self.project_slug)
            sources_context = self._read_sources_context(self.project_slug)
            _pm_longform = getattr(self, "_last_project_mode", {})
            topic_type_longform = str(_pm_longform.get("topic_type", "general")).strip().lower() if isinstance(_pm_longform, dict) else "general"
            longform_result = self._run_registered_agent(
                "make_longform",
                self._make_agent_task(
                    lane="make_longform",
                    text=text,
                    context={
                        "type_id": kind,
                        "topic_type": topic_type_longform,
                        "research_context": research_context,
                        "raw_notes_context": raw_notes_context,
                        "sources_context": sources_context,
                    },
                    cancel_checker=getattr(self, "_last_cancel_checker", None),
                    progress_callback=getattr(self, "_last_progress_callback", None),
                ),
            )
            longform_body = str(longform_result.get("body", "")).strip()
            if not longform_body:
                longform_body = f"# {kind.replace('_', ' ').title()}\n\n(Longform pool returned no content.)\n"
            warning_banner = str(longform_result.get("warning_banner", "")).strip()
            stamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
            _LONGFORM_DIRS = {
                "video_script": "VideoScripts", "newsletter": "Newsletters",
                "press_release": "PressReleases", "guide": "Guides", "tutorial": "Tutorials",
            }
            dir_name = _LONGFORM_DIRS.get(kind, "Essays-Scripts")
            deliverable_root = self.repo_root / "Projects" / dir_name / self.project_slug
            deliverable_root.mkdir(parents=True, exist_ok=True)
            out_path = deliverable_root / f"{stamp}_{kind}.md"
            out_path.write_text(longform_body + "\n", encoding="utf-8")
            self.bus.emit(
                "orchestrator",
                "make_deliverable_written",
                {
                    "project": self.project_slug,
                    "kind": kind,
                    "path": str(out_path),
                    "warning_banner": warning_banner,
                },
            )
            return {
                "ok": longform_result.get("ok", True),
                "message": longform_result.get("message", f"Longform {kind.replace('_', ' ')} complete."),
                "path": str(out_path),
                "delivery_kind": kind,
                "sections_written": longform_result.get("sections_written", []),
                "word_count": len(longform_body.split()),
                "warning_banner": warning_banner,
            }

        # --- Desktop app: .NET 8 + Avalonia ---
        if kind == "desktop_app":
            research_context = self._merge_make_seed_context(
                self._read_research_context(self.project_slug, max_summaries=2, chars_per_summary=4000),
                seed_artifact_text,
            )
            desktop_model = str(lane_model_config(self.repo_root, "make_desktop_app").get("model", "")).strip()
            lock_model = desktop_model or "qwen3-coder:30b-a3b-q4_K_M"
            from shared_tools.premium_model_lock import PremiumModelLock
            premium_lock = PremiumModelLock(self.repo_root, client=self.ollama)
            lease = premium_lock.acquire(lock_model, timeout_sec=180.0)
            try:
                out = self._run_registered_agent(
                    "make_desktop_app",
                    self._make_agent_task(
                        lane="make_desktop_app",
                        text=text,
                        context={
                            "research_context": research_context,
                        },
                        cancel_checker=getattr(self, "_last_cancel_checker", None),
                        progress_callback=getattr(self, "_last_progress_callback", None),
                    ),
                )
            finally:
                try:
                    premium_lock.release(lease, force_unload=True)
                except Exception:
                    pass
            out["delivery_kind"] = kind
            self.bus.emit(
                "orchestrator",
                "make_deliverable_written",
                {"project": self.project_slug, "kind": kind, "path": out.get("path", "")},
            )
            return out

        # --- Tool / script ---
        if kind in {"tool", "script"}:
            research_context = self._merge_make_seed_context(
                self._read_research_context(self.project_slug, max_summaries=2, chars_per_summary=4000),
                seed_artifact_text,
            )
            tool_model = str(lane_model_config(self.repo_root, "make_tool").get("model", "")).strip()
            lock_model = tool_model or "qwen3-coder:30b-a3b-q4_K_M"
            from shared_tools.premium_model_lock import PremiumModelLock
            premium_lock = PremiumModelLock(self.repo_root, client=self.ollama)
            lease = premium_lock.acquire(lock_model, timeout_sec=180.0)
            try:
                out = self._run_registered_agent(
                    "make_tool",
                    self._make_agent_task(
                        lane="make_tool",
                        text=text,
                        context={
                            "research_context": research_context,
                        },
                        cancel_checker=getattr(self, "_last_cancel_checker", None),
                        progress_callback=getattr(self, "_last_progress_callback", None),
                    ),
                )
            finally:
                try:
                    premium_lock.release(lease, force_unload=True)
                except Exception:
                    pass
            out["delivery_kind"] = kind
            self.bus.emit(
                "orchestrator",
                "make_deliverable_written",
                {"project": self.project_slug, "kind": kind, "path": out.get("path", "")},
            )
            return out

        # --- Fallback: unknown or generic document kinds ---
        deliverable_root = self.repo_root / "Projects" / "Essays-Scripts" / self.project_slug
        deliverable_root.mkdir(parents=True, exist_ok=True)
        stamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        out_path = deliverable_root / f"{stamp}_{kind}.md"
        summary_path, summary_preview = self._latest_research_summary_preview(self.project_slug)

        cfg = lane_model_config(self.repo_root, "orchestrator_reasoning")
        model = str(cfg.get("model", "")).strip()
        if not model:
            body = (
                f"# {kind.replace('_', ' ').title()} Draft\n\n"
                "Model routing missing for orchestrator_reasoning.\n"
                "Please configure a model, then rerun this MAKE request."
            )
            out_path.write_text(body, encoding="utf-8")
            return {
                "ok": False,
                "message": "MAKE lane could not render a model-driven deliverable.",
                "path": str(out_path),
                "delivery_kind": kind,
            }

        system_prompt = (
            "You are Oathweaver MAKE lane. "
            "Your job is execution: turn existing project research/context into a concrete deliverable. "
            "Do not ask follow-up questions. Make the best defensible draft now."
        )
        user_prompt = (
            f"Project: {self.project_slug}\n"
            f"Deliverable kind: {kind}\n\n"
            f"User request:\n{text.strip()}\n\n"
            "Produce a concise, structured markdown document with clear sections and action items.\n\n"
            "Constraints:\n"
            "- Output markdown only.\n"
            "- Keep it practical and directly usable.\n"
            "- If facts are uncertain, mark assumptions clearly.\n\n"
            f"Latest research summary path: {summary_path or 'none'}\n"
            f"Latest research summary preview:\n{summary_preview.strip()[:6500] or '(none)'}\n"
        )
        seed_block = str(seed_artifact_text or "").strip()
        if seed_block:
            user_prompt = f"{seed_block}\n\n{user_prompt}"
        body = self.ollama.chat(
            model=model,
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            prior_messages=[],
            temperature=float(cfg.get("temperature", 0.2)),
            num_ctx=int(cfg.get("num_ctx", 16384)),
            think=bool(cfg.get("think", False)),
            timeout=int(cfg.get("timeout_sec", 0) or 0),
            retry_attempts=int(cfg.get("retry_attempts", 6)),
            retry_backoff_sec=float(cfg.get("retry_backoff_sec", 1.6)),
            fallback_models=cfg.get("fallback_models", []) if isinstance(cfg.get("fallback_models", []), list) else [],
        )
        out_path.write_text(body.strip() + "\n", encoding="utf-8")
        self.bus.emit(
            "orchestrator",
            "make_deliverable_written",
            {"project": self.project_slug, "kind": kind, "path": str(out_path)},
        )
        return {
            "ok": True,
            "message": f"MAKE lane drafted a {kind.replace('_', ' ')} deliverable.",
            "path": str(out_path),
            "delivery_kind": kind,
            "summary_path": summary_path,
        }

    def _format_research_artifacts_block(self, out: dict) -> str:
        lines: list[str] = ["---"]
        reliability = out.get("reliability", {})
        if isinstance(reliability, dict) and reliability:
            good = int(reliability.get("good", 0))
            weak = int(reliability.get("weak", 0))
            failed = int(reliability.get("failed", 0))
            profile = str(out.get("analysis_profile", "")).strip().replace("_", " ")
            rel_line = f"Agents: {good} good / {weak} weak / {failed} failed"
            if profile:
                rel_line = f"{rel_line}  |  Profile: {profile}"
            lines.append(rel_line)
        file_lines: list[str] = []

        def _file_link_line(label: str, raw_path: str) -> str:
            from urllib.parse import quote
            path_text = str(raw_path or "").strip()
            if not path_text:
                return ""
            rel_text = path_text
            try:
                rel_text = str(Path(path_text).relative_to(self.repo_root))
            except Exception:
                pass
            link_url = f"/api/files/read?path={quote(rel_text, safe='/._-')}"
            name = Path(path_text).name or rel_text
            return f"  {label} → [{name}]({link_url})"

        summary_path = str(out.get("summary_path", "")).strip()
        raw_path = str(out.get("raw_path", "")).strip()
        critique_path = str(out.get("critique_path", "")).strip()
        web_details = out.get("web_details", {})
        source_path = str(web_details.get("source_path", "")).strip() if isinstance(web_details, dict) else ""
        if summary_path:
            row = _file_link_line("Summary  ", summary_path)
            if row:
                file_lines.append(row)
        if raw_path:
            row = _file_link_line("Raw Notes", raw_path)
            if row:
                file_lines.append(row)
        if critique_path:
            row = _file_link_line("Critique ", critique_path)
            if row:
                file_lines.append(row)
        if source_path:
            row = _file_link_line("Sources  ", source_path)
            if row:
                file_lines.append(row)
        if file_lines:
            lines.append("Files:")
            lines.extend(file_lines)
        return "\n".join(lines)

    def _queue_action_proposals(self, reply: str) -> None:
        """Extract actionable next steps from synthesis and queue as approval proposals."""
        try:
            from agents_research.synthesizer import extract_action_proposals
            proposals = extract_action_proposals(reply)
            for p in proposals:
                self.approval_gate.create_action_proposal(
                    action_type=str(p.get("action_type", "create_task")),
                    action_payload={"title": str(p.get("title", "")), "notes": str(p.get("notes", ""))},
                    source="synthesis",
                    project_slug=self.project_slug,
                    title=str(p.get("title", "")),
                )
        except Exception:
            pass

    def _append_daymarker_note(self, reply: str, note: str) -> str:
        text = str(reply or "").strip()
        addon = str(note or "").strip()
        if not addon:
            return text
        if addon in text:
            return text
        if not text:
            return addon
        return f"{text}\n{addon}"

    def _is_reminder_only_request(self, text: str) -> bool:
        return is_reminder_only_request(text, self._extract_reminder_from_text)

    def _is_event_only_request(self, text: str) -> bool:
        return is_event_only_request(text)

    def handle_message(
        self,
        text: str,
        history: list[dict[str, str]] | None = None,
        *,
        project_mode: dict[str, Any] | None = None,
        cancel_checker=None,
        pause_checker=None,
        yield_checker=None,
        progress_callback=None,
        conversation_summary: str = "",
        seed_artifact_text: str = "",
        force_research: bool = False,
        force_make: bool = False,
        force_plan: bool = False,
        thread_id: str = "",
        details_sink: dict[str, Any] | None = None,
        topic_context: str = "",
        reply_to: dict[str, Any] | None = None,
    ) -> str:
        self.bus.emit("orchestrator", "message_received", {"project": self.project_slug})
        incoming_text = str(text or "").strip()
        normalized_text = self._strip_oathweaver_vocative_prefix(incoming_text)
        text = normalized_text or incoming_text

        def _is_cancelled() -> bool:
            if callable(cancel_checker):
                try:
                    return bool(cancel_checker())
                except Exception:
                    return False
            return False

        def _progress(stage: str, detail: str = "") -> None:
            if not callable(progress_callback):
                return
            try:
                progress_callback(stage, detail)
            except Exception:
                pass

        if _is_cancelled():
            return "Request cancelled before orchestration started."

        _progress("orchestrator_received", "Message routed into orchestrator pipeline.")
        perf = PerfTrace(self.repo_root, category="orchestrator_turn")
        perf.set_meta(project=self.project_slug, user_text=text[:180])
        perf.start("route_and_context")
        if self._is_oathweaver_self_query(incoming_text):
            return self._oathweaver_identity_reply()
        # NOTE: conversation_summary is injected into project_context below (after it is built),
        # not prepended to user text — so the router and lane handlers see clean user input.
        legacy_memory_writes = str(os.environ.get("OATHWEAVERX_ENABLE_LEGACY_MEMORY_WRITES", "0")).strip().lower() in {"1", "true", "yes", "on"}
        if legacy_memory_writes:
            facts_before = self.project_memory.get_facts(self.project_slug)
            if isinstance(history, list):
                scan_rows = history if not facts_before else history[-30:]
                for row in scan_rows:
                    if not isinstance(row, dict):
                        continue
                    role = str(row.get("role", "")).strip().lower()
                    if role != "user":
                        continue
                    content = str(row.get("content", "")).strip()
                    if not content:
                        continue
                    self.project_memory.ingest_text(self.project_slug, content)
            self.project_memory.ingest_text(self.project_slug, text)
        if force_research:
            reminder_note = ""
            event_note = ""
        else:
            reminder_note = self._capture_daymarker_reminder(text)
            event_note = self._capture_daymarker_event(text, history=history)
        forage_seed_norm = ""
        forage_summary_before = ""
        if force_research:
            forage_gate = self._forage_gate(text)
            forage_seed_norm = str(forage_gate.get("seed_norm", "")).strip()
            if not bool(forage_gate.get("allowed", True)):
                reason = str(forage_gate.get("reason", "")).strip()
                prior = forage_gate.get("prior", {}) if isinstance(forage_gate.get("prior", {}), dict) else {}
                prior_summary = str(prior.get("summary_path", "")).strip()
                if prior_summary:
                    try:
                        prior_summary = str(Path(prior_summary).resolve().relative_to(self.repo_root))
                    except Exception:
                        pass
                if reason == "dedup":
                    if prior_summary:
                        return (
                            "I already ran that forage seed in the last hour. "
                            f"Reusing the previous result: `{prior_summary}`.\n\n"
                            "If you want a fresh run anyway, include 'refresh' in your request."
                        )
                    return (
                        "I already ran that forage seed in the last hour, so I skipped a duplicate run.\n\n"
                        "If you want a fresh run anyway, include 'refresh' in your request."
                    )
                return (
                    "Foraging rate limit reached: max 3 executions in a rolling 10-minute window.\n\n"
                    "Wait a few minutes, then retry."
                )
        self._maybe_auto_refresh_project_facts(history)
        project_context = self.project_memory.summary_text(self.project_slug, limit_chars=2600)
        if topic_context.strip():
            project_context = (topic_context.strip() + "\n\n" + project_context).strip()
        _context_analysis, household_context, context_guidance = self._context_bundle_for_query(
            text,
            household_chars=1300,
        )
        if household_context:
            project_context = (household_context + "\n\n" + project_context).strip()
        if context_guidance:
            project_context = (context_guidance + "\n\n" + project_context).strip()
        retrieved_context = self.embedding_memory.context_text(self.project_slug, text, limit=2)
        if retrieved_context:
            project_context = (project_context + "\n\n" + retrieved_context).strip()
        try:
            _active_mode = self.pipeline_store.get(self.project_slug) or {}
            _active_domain = str(_active_mode.get("topic_type", "")).strip().lower()
            library_context = self.library_service.context_text(
                text,
                project_slug=self.project_slug,
                topic_id=str(_active_mode.get("topic_id", "")).strip(),
                domain=_active_domain,
                limit=5,
            )
            if library_context:
                project_context = (project_context + "\n\n" + library_context).strip()
        except Exception:
            pass
        # Watchtower appended at the END of context so it receives recency attention
        # from the model (time-sensitive research cards should be read close to the user message).
        _briefing_context = self._watchtower_context_for_query()
        if _briefing_context:
            project_context = (project_context + "\n\n" + _briefing_context).strip()
        # Conversation summary appended last so it's close to the user message in context.
        if conversation_summary:
            _summary_block = f"Prior conversation context:\n{conversation_summary.strip()}"
            project_context = (project_context + "\n\n" + _summary_block).strip()

        if self._is_casual_conversation_turn(text):
            self.bus.emit("orchestrator", "conversation_short_circuit", {"project": self.project_slug})
            if self._chat_via_graph_enabled():
                try:
                    graph_result = invoke_chat_turn_graph(
                        self,
                        text=text,
                        history=history,
                        cancel_checker=cancel_checker,
                        progress_callback=progress_callback,
                        thread_id=str(thread_id or "").strip(),
                    )
                    reply = str(graph_result.get("reply", "")).strip()
                    if isinstance(details_sink, dict):
                        details_sink["turn_graph"] = {
                            "graph_used": bool(graph_result.get("graph_used", False)),
                            "state": graph_result.get("state", {}),
                        }
                    if reply:
                        return reply
                except Exception:
                    pass
            return self.conversation_reply(
                text,
                history=history,
                project=self.project_slug,
                reply_to=reply_to,
            )

        pipeline = project_mode if isinstance(project_mode, dict) else self.pipeline_store.get(self.project_slug)
        mode = str(pipeline.get("mode", "discovery")).strip().lower() or "discovery"
        target = str(pipeline.get("target", "auto")).strip().lower() or "auto"
        topic_type = str(pipeline.get("topic_type", "general")).strip().lower() or "general"
        # Build a brief recent-context snippet for the LLM router so it can disambiguate
        # follow-up messages without needing to read the full history.
        _routing_recent_ctx = ""
        if isinstance(history, list):
            _routing_turns: list[str] = []
            for _row in history[-6:]:
                _role = str(_row.get("role", "")).strip().lower()
                _content = str(_row.get("content", "")).strip()[:100]
                if _role in {"user", "assistant"} and _content:
                    _routing_turns.append(f"{_role.upper()}: {_content}")
            if _routing_turns:
                _routing_recent_ctx = "Recent conversation:\n" + "\n".join(_routing_turns)
        turn_plan = self.turn_planner.plan(
            text,
            project=self.project_slug,
            topic_type=topic_type,
            client=self.ollama,
            model_cfg=lane_model_config(self.repo_root, "orchestrator_reasoning"),
            recent_context=_routing_recent_ctx,
        )
        lane = turn_plan.lane
        inferred_target = self._infer_delivery_target(text, target, mode=mode)
        if not force_research and mode == "make" and lane in {"research", "project"}:
            if _has_build_intent(text):
                lane = _make_lane_for_target(inferred_target)
        if force_research:
            lane = "research"
        elif force_plan:
            lane = "make_plan"
        elif force_make:
            lane = _make_lane_for_target(inferred_target)
        elif turn_plan.lane_override and lane in {"research", "project", "personal"}:
            lane = turn_plan.lane_override
        if lane in {"research", "project"} and self._personal_context_detected(_context_analysis):
            lane = "conversation"
            self.bus.emit(
                "orchestrator",
                "personal_context_guard",
                {"project": self.project_slug, "reason": "context_gate_forced_conversation"},
            )
        resolved_domain = self._resolved_pipeline_domain(turn_plan)
        query_mode = turn_plan.query_mode
        query_complexity = turn_plan.complexity
        kernel = self.project_kernel_store.update_for_turn(
            project_id=self.project_slug,
            lane=lane,
            topic_type=topic_type,
            query_text=text,
            query_mode=query_mode,
            make_type=turn_plan.make_type or inferred_target,
            make_intent=turn_plan.make_intent or query_mode,
            specialist_stages=[],
        )
        if isinstance(details_sink, dict):
            details_sink["project_kernel"] = kernel.as_dict()
        perf.end("route_and_context")
        perf.set_meta(lane=lane, query_mode=query_mode, query_complexity=query_complexity)
        _progress("lane_routed", f"Pipeline: {lane_to_pipeline(lane)} | mode={query_mode} | complexity={query_complexity}")
        self.bus.emit("orchestrator", "routed", {"lane": lane, "project": self.project_slug})

        if reminder_note and self._is_reminder_only_request(text):
            self.bus.emit("orchestrator", "reminder_short_circuit", {"lane": lane, "project": self.project_slug})
            return self._append_daymarker_note(reminder_note, event_note)
        if event_note and self._is_event_only_request(text):
            self.bus.emit("orchestrator", "event_short_circuit", {"lane": lane, "project": self.project_slug})
            return self._append_daymarker_note(event_note, reminder_note)

        if self.approval_gate.requires_approval(text, lane):
            request_id = self.approval_gate.create_request(lane, text, self.project_slug)
            self.bus.emit("orchestrator", "approval_requested", {"id": request_id, "lane": lane})
            reply = (
                "I drafted this personal action, but it is approval-gated. "
                f"Use /approve {request_id} to allow or /reject {request_id} to block."
            )
            reply = self._append_daymarker_note(reply, event_note)
            return self._append_daymarker_note(reply, reminder_note)

        pipeline_reply = self._execute_pipeline_turn(
            lane=lane,
            text=text,
            history=history,
            topic_type=topic_type,
            query_mode=query_mode,
            query_complexity=query_complexity,
            inferred_target=inferred_target,
            mode=mode,
            turn_plan=turn_plan,
            force_research=force_research,
            cancel_checker=cancel_checker,
            pause_checker=pause_checker,
            yield_checker=yield_checker,
            progress_callback=progress_callback,
            reminder_note=reminder_note,
            event_note=event_note,
            details_sink=details_sink,
            household_context=household_context,
            resolved_domain=resolved_domain,
        )
        if pipeline_reply is not None:
            return pipeline_reply

        if lane == "conversation":
            if serious_mode_enabled():
                return self.research_service.execute_project_lane(
                    self,
                    text=text,
                    history=history,
                    topic_type=topic_type,
                    cancel_checker=cancel_checker,
                    pause_checker=pause_checker,
                    yield_checker=yield_checker,
                    progress_callback=progress_callback,
                    reminder_note=reminder_note,
                    event_note=event_note,
                    details_sink=details_sink,
                )
            if self._chat_via_graph_enabled():
                try:
                    graph_result = invoke_chat_turn_graph(
                        self,
                        text=text,
                        history=history,
                        precomputed_route={
                            "lane_hint": lane,
                            "domain": resolved_domain,
                            "make_type": str(getattr(turn_plan, "make_type", "") or ""),
                        },
                        cancel_checker=cancel_checker,
                        progress_callback=progress_callback,
                        thread_id=str(thread_id or "").strip(),
                    )
                    reply = str(graph_result.get("reply", "")).strip()
                    if isinstance(details_sink, dict):
                        details_sink["turn_graph"] = {
                            "graph_used": bool(graph_result.get("graph_used", False)),
                            "state": graph_result.get("state", {}),
                        }
                    if reply:
                        return reply
                except Exception as exc:
                    self.bus.emit(
                        "orchestrator",
                        "turn_graph_fallback",
                        {"project": self.project_slug, "error": str(exc)[:220]},
                    )
            return self.conversation_reply(
                text,
                history=history,
                project=self.project_slug,
                reply_to=reply_to,
            )

        if lane == "research":
            if force_research:
                forage_summary_before = self._latest_research_summary_path()
            reply = self.research_service.execute_research_lane(
                self,
                text=text,
                history=history,
                topic_type=topic_type,
                turn_plan=turn_plan,
                force_research=force_research,
                cancel_checker=cancel_checker,
                pause_checker=pause_checker,
                yield_checker=yield_checker,
                progress_callback=progress_callback,
                perf=perf,
                reminder_note=reminder_note,
                event_note=event_note,
                lane=lane,
                details_sink=details_sink,
            )
            if force_research and forage_seed_norm:
                summary_after = self._latest_research_summary_path()
                summary_path = summary_after or forage_summary_before
                self._append_forage_log(
                    {
                        "project": self.project_slug,
                        "seed": text,
                        "seed_norm": forage_seed_norm,
                        "status": "cancelled" if "cancelled" in str(reply).lower() else "executed",
                        "summary_path": summary_path,
                    }
                )
            return reply
        if lane == "ui":
            if _is_cancelled():
                return "Request cancelled before UI lane execution started."
            self._last_project_mode = pipeline
            self._last_progress_callback = progress_callback
            self._last_cancel_checker = cancel_checker
            out = self._run_make_delivery(
                text=text,
                history=history,
                target=target,
                mode=mode,
                seed_artifact_text=seed_artifact_text,
            )
            fallback = f"{out.get('message', 'UI lane completed.')} Output: {out.get('path', '')}"
            internal_reply = self._orchestrator_finalize(text, lane, out, fallback, topic_type=topic_type)
            reply = self._weaver_relay(
                user_text=text,
                lane=lane,
                internal_reply=internal_reply,
                worker_result=out,
                topic_type=topic_type,
            )
            reply = self._append_daymarker_note(reply, event_note)
            reply = self._append_daymarker_note(reply, reminder_note)
            return self._complete_turn(
                user_text=text,
                lane=lane,
                reply_text=reply,
                worker_result=out,
                context_feedback=self._context_feedback(
                    user_text=text,
                    reply_text=reply,
                    household_context=household_context,
                ),
            )

        if lane == "make_app":
            if _is_cancelled():
                return "Request cancelled before make_app lane execution started."
            self._last_project_mode = pipeline
            self._last_progress_callback = progress_callback
            self._last_cancel_checker = cancel_checker
            out = self._run_make_delivery(
                text=text,
                history=history,
                target=target,
                mode=mode,
                seed_artifact_text=seed_artifact_text,
            )
            fallback = f"{out.get('message', 'App build completed.')} Output: {out.get('path', '')}"
            reply = self._make_summary_reply(lane=lane, out=out, fallback=fallback)
            reply = self._append_daymarker_note(reply, event_note)
            reply = self._append_daymarker_note(reply, reminder_note)
            return self._complete_turn(
                user_text=text,
                lane=lane,
                reply_text=reply,
                worker_result=out,
                context_feedback=self._context_feedback(
                    user_text=text,
                    reply_text=reply,
                    household_context=household_context,
                ),
            )

        if lane == "make_tool":
            if _is_cancelled():
                return "Request cancelled before make_tool lane execution started."
            self._last_project_mode = pipeline
            self._last_progress_callback = progress_callback
            self._last_cancel_checker = cancel_checker
            research_context = self._merge_make_seed_context(
                self._read_research_context(self.project_slug, max_summaries=2, chars_per_summary=4000),
                seed_artifact_text,
            )
            out = self._run_registered_agent(
                "make_tool",
                self._make_agent_task(
                    lane="make_tool",
                    text=text,
                    context={
                        "research_context": research_context,
                    },
                    history=history,
                    cancel_checker=cancel_checker,
                    progress_callback=progress_callback,
                ),
            )
            fallback = f"{out.get('message', 'Tool build completed.')} Output: {out.get('path', '')}"
            reply = self._make_summary_reply(lane=lane, out=out, fallback=fallback)
            reply = self._append_daymarker_note(reply, event_note)
            reply = self._append_daymarker_note(reply, reminder_note)
            return self._complete_turn(
                user_text=text,
                lane=lane,
                reply_text=reply,
                worker_result=out,
                context_feedback=self._context_feedback(
                    user_text=text,
                    reply_text=reply,
                    household_context=household_context,
                ),
            )

        if lane == "make_doc":
            if _is_cancelled():
                return "Request cancelled before MAKE lane execution started."
            self._last_project_mode = pipeline
            self._last_progress_callback = progress_callback
            self._last_cancel_checker = cancel_checker
            out = self._run_make_delivery(
                text=text,
                history=history,
                target=target,
                mode=mode,
                seed_artifact_text=seed_artifact_text,
            )
            fallback = f"{out.get('message', 'MAKE lane completed.')} Output: {out.get('path', '')}"
            reply = self._make_summary_reply(lane=lane, out=out, fallback=fallback)
            reply = self._append_daymarker_note(reply, event_note)
            reply = self._append_daymarker_note(reply, reminder_note)
            return self._complete_turn(
                user_text=text,
                lane="project",
                reply_text=reply,
                worker_result=out,
                context_feedback=self._context_feedback(
                    user_text=text,
                    reply_text=reply,
                    household_context=household_context,
                ),
            )

        if lane == "make_plan":
            if _is_cancelled():
                return "Request cancelled before make_plan lane execution started."
            self._last_project_mode = pipeline
            self._last_progress_callback = progress_callback
            self._last_cancel_checker = cancel_checker
            out = self._run_make_plan(
                text=text,
                target=target,
                mode=mode,
            )
            fallback = f"{out.get('message', 'Plan generation completed.')} Output: {out.get('path', '')}"
            reply = self._make_summary_reply(lane=lane, out=out, fallback=fallback)
            reply = self._append_daymarker_note(reply, event_note)
            reply = self._append_daymarker_note(reply, reminder_note)
            return self._complete_turn(
                user_text=text,
                lane=lane,
                reply_text=reply,
                worker_result=out,
                context_feedback=self._context_feedback(
                    user_text=text,
                    reply_text=reply,
                    household_context=household_context,
                ),
            )

        if lane in {"make_creative", "make_content", "make_specialist"}:
            if _is_cancelled():
                return f"Request cancelled before {lane} lane execution started."
            self._last_project_mode = pipeline
            self._last_progress_callback = progress_callback
            self._last_cancel_checker = cancel_checker
            out = self._run_make_delivery(
                text=text,
                history=history,
                target=target,
                mode=mode,
                seed_artifact_text=seed_artifact_text,
            )
            fallback = f"{out.get('message', 'MAKE lane completed.')} Output: {out.get('path', '')}"
            reply = self._make_summary_reply(lane=lane, out=out, fallback=fallback)
            reply = self._append_daymarker_note(reply, event_note)
            reply = self._append_daymarker_note(reply, reminder_note)
            return self._complete_turn(
                user_text=text,
                lane=lane,
                reply_text=reply,
                worker_result=out,
                context_feedback=self._context_feedback(
                    user_text=text,
                    reply_text=reply,
                    household_context=household_context,
                ),
            )

        if lane == "make_longform":
            if _is_cancelled():
                return "Request cancelled before make_longform lane execution started."
            self._last_project_mode = pipeline
            self._last_progress_callback = progress_callback
            self._last_cancel_checker = cancel_checker
            research_context = self._merge_make_seed_context(
                self._read_research_context(self.project_slug, max_summaries=2, chars_per_summary=4000),
                seed_artifact_text,
            )
            raw_notes_context = self._read_raw_notes_context(self.project_slug)
            sources_context = self._read_sources_context(self.project_slug)
            longform_result = self._run_registered_agent(
                "make_longform",
                self._make_agent_task(
                    lane="make_longform",
                    text=text,
                    context={
                        "type_id": target,
                        "research_context": research_context,
                        "raw_notes_context": raw_notes_context,
                        "sources_context": sources_context,
                    },
                    cancel_checker=cancel_checker,
                    progress_callback=progress_callback,
                ),
            )
            longform_body = str(longform_result.get("body", "")).strip()
            if not longform_body:
                longform_body = f"# {target.replace('_', ' ').title()}\n\n(Longform pool returned no content.)\n"
            stamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
            _LONGFORM_DIRS_L = {
                "video_script": "VideoScripts", "newsletter": "Newsletters",
                "press_release": "PressReleases", "guide": "Guides", "tutorial": "Tutorials",
            }
            dir_name = _LONGFORM_DIRS_L.get(target, "Essays-Scripts")
            deliverable_root = self.repo_root / "Projects" / dir_name / self.project_slug
            deliverable_root.mkdir(parents=True, exist_ok=True)
            out_path = deliverable_root / f"{stamp}_{target}.md"
            out_path.write_text(longform_body + "\n", encoding="utf-8")
            self.bus.emit(
                "orchestrator",
                "make_deliverable_written",
                {"project": self.project_slug, "kind": target, "path": str(out_path)},
            )
            out = {
                "ok": longform_result.get("ok", True),
                "message": longform_result.get("message", f"Longform {target.replace('_', ' ')} complete."),
                "path": str(out_path),
                "delivery_kind": target,
                "sections_written": longform_result.get("sections_written", []),
                "word_count": len(longform_body.split()),
            }
            fallback = f"{out.get('message', 'Longform build completed.')} Output: {out_path}"
            reply = self._make_summary_reply(lane=lane, out=out, fallback=fallback)
            reply = self._append_daymarker_note(reply, event_note)
            reply = self._append_daymarker_note(reply, reminder_note)
            return self._complete_turn(
                user_text=text,
                lane=lane,
                reply_text=reply,
                worker_result=out,
                context_feedback=self._context_feedback(
                    user_text=text,
                    reply_text=reply,
                    household_context=household_context,
                ),
            )

        if lane == "make_desktop_app":
            if _is_cancelled():
                return "Request cancelled before make_desktop_app lane execution started."
            self._last_project_mode = pipeline
            self._last_progress_callback = progress_callback
            self._last_cancel_checker = cancel_checker
            research_context = self._merge_make_seed_context(
                self._read_research_context(self.project_slug, max_summaries=2, chars_per_summary=4000),
                seed_artifact_text,
            )
            out = self._run_registered_agent(
                "make_desktop_app",
                self._make_agent_task(
                    lane="make_desktop_app",
                    text=text,
                    context={
                        "research_context": research_context,
                    },
                    cancel_checker=cancel_checker,
                    progress_callback=progress_callback,
                ),
            )
            fallback = f"{out.get('message', 'Desktop app build completed.')} Output: {out.get('path', '')}"
            reply = self._make_summary_reply(lane=lane, out=out, fallback=fallback)
            reply = self._append_daymarker_note(reply, event_note)
            reply = self._append_daymarker_note(reply, reminder_note)
            return self._complete_turn(
                user_text=text,
                lane=lane,
                reply_text=reply,
                worker_result=out,
                context_feedback=self._context_feedback(
                    user_text=text,
                    reply_text=reply,
                    household_context=household_context,
                ),
            )

        if lane == "personal":
            return "Personal assistant lane is not available in this Oathweaver build."

        return self.research_service.execute_project_lane(
            self,
            text=text,
            history=history,
            topic_type=topic_type,
            cancel_checker=cancel_checker,
            pause_checker=pause_checker,
            yield_checker=yield_checker,
            progress_callback=progress_callback,
            reminder_note=reminder_note,
            event_note=event_note,
            details_sink=details_sink,
        )


    def workspace_tree_text(self, rel_path: str = ".", max_depth: int = 2) -> str:
        try:
            return self.workspace_tools.tree_text(self.project_slug, rel_path=rel_path, max_depth=max_depth)
        except Exception as exc:
            return f"Workspace tree failed: {exc}"

    def workspace_read_text(self, rel_path: str, max_chars: int = 12000) -> str:
        try:
            return self.workspace_tools.read_text(self.project_slug, rel_path=rel_path, max_chars=max_chars)
        except Exception as exc:
            return f"Workspace read failed: {exc}"

    def workspace_search_text(self, query: str, rel_glob: str = "*", limit: int = 20) -> str:
        try:
            return self.workspace_tools.search_text(self.project_slug, query=query, rel_glob=rel_glob, limit=limit)
        except Exception as exc:
            return f"Workspace search failed: {exc}"

    def workspace_patch_text(self, rel_path: str, instruction: str) -> str:
        try:
            result = self.workspace_tools.propose_patch(
                self.project_slug,
                rel_path=rel_path,
                instruction=instruction,
                approval_gate=self.approval_gate,
                source="workspace_tools",
            )
        except Exception as exc:
            return f"Workspace patch proposal failed: {exc}"
        return result.get("message", "Workspace patch proposal failed.")

    def workspace_patch_batch_text(self, rel_paths: list[str], instruction: str) -> str:
        try:
            result = self.workspace_tools.propose_patch_batch(
                self.project_slug,
                rel_paths=rel_paths,
                instruction=instruction,
                approval_gate=self.approval_gate,
                source="workspace_tools",
            )
        except Exception as exc:
            return f"Workspace batch patch proposal failed: {exc}"
        return result.get("message", "Workspace batch patch proposal failed.")

    def workspace_pending_patches_text(self, limit: int = 20) -> str:
        try:
            return self.workspace_tools.list_patch_proposals_text(self.approval_gate, limit=limit)
        except Exception as exc:
            return f"Workspace patch listing failed: {exc}"

    def approve_action_proposal(self, proposal_id: str) -> str:
        result = self.approval_gate.execute_proposal(proposal_id, self.repo_root)
        if result.get("ok"):
            self.bus.emit("orchestrator", "action_proposal_executed", {"id": proposal_id})
        return str(result.get("message", "Unknown action proposal result."))

    def pending_approvals_text(self) -> str:
        pending = self.approval_gate.list_pending()
        if not pending:
            return "No pending approvals."
        lines = ["Pending approvals:"]
        for item in pending:
            lines.append(f"- {item['id']} | lane={item['lane']} | text={item['text']}")
        return "\n".join(lines)

    def decide_approval(self, request_id: str, approved: bool) -> str:
        stored = self.approval_gate.get_request(request_id)
        ok = self.approval_gate.decide(request_id, approved)
        if not ok:
            return f"Approval id not found: {request_id}"
        event = "approval_approved" if approved else "approval_rejected"
        self.bus.emit("orchestrator", event, {"id": request_id})
        base_msg = f"Decision recorded for {request_id}: {'approved' if approved else 'rejected'}."
        if not approved or stored is None:
            return base_msg
        return f"{base_msg}\n\nPersonal assistant lane is not available in this Oathweaver build."

    def create_handoff(self, target: str, request_text: str) -> str:
        return _handoff_mgr.create_handoff(self.handoff_queue, self.bus, self.project_slug, target, request_text)

    def handoff_pending_text(self) -> str:
        return _handoff_mgr.handoff_pending_text(self.handoff_queue)

    def approve_handoff(self, request_id: str, reason: str = "") -> str:
        return _handoff_mgr.approve_handoff(self.handoff_queue, self.bus, request_id, reason)

    def deny_handoff(self, request_id: str, reason: str) -> str:
        return _handoff_mgr.deny_handoff(self.handoff_queue, self.bus, request_id, reason)

    def handoff_inbox_text(self, target: str | None = None) -> str:
        return _handoff_mgr.handoff_inbox_text(self.handoff_queue, target)

    def handoff_sync(self) -> str:
        return _handoff_mgr.handoff_sync(self.handoff_queue, self.bus)

    def handoff_monitor_text(self, limit: int = 50) -> str:
        return _handoff_mgr.handoff_monitor_text(self.handoff_queue, limit=limit)

    def handoff_outbox_text(self, target: str | None = None, limit: int = 20) -> str:
        return _handoff_mgr.handoff_outbox_text(self.learning_engine, target=target, limit=limit)

    def learn_outbox(self, target: str, lane_hint: str | None = None, limit: int = 5) -> str:
        return _lesson_mgr.learn_outbox(self.learning_engine, self.bus, target, lane_hint=lane_hint, limit=limit)

    def learn_outbox_one(self, target: str, thread_id: str, lane_hint: str | None = None) -> dict[str, Any]:
        return _lesson_mgr.learn_outbox_one(self.learning_engine, self.bus, target, thread_id, lane_hint=lane_hint)

    def lessons_text(self, lane: str | None = None, limit: int = 10) -> str:
        return _lesson_mgr.lessons_text(self.learning_engine, lane=lane, limit=limit)

    def lesson_guidance_text(self, lane: str | None = None, limit: int = 5) -> str:
        return _lesson_mgr.lesson_guidance_text(self.learning_engine, lane=lane, limit=limit)

    def lesson_reinforce(self, lesson_id: str, direction: str, note: str = "") -> str:
        return _lesson_mgr.lesson_reinforce(self.learning_engine, self.bus, lesson_id, direction, note)

    def lesson_expire(self, lesson_id: str) -> str:
        return _lesson_mgr.lesson_expire(self.learning_engine, self.bus, lesson_id)

    def reflection_open_text(self, limit: int = 10) -> str:
        return _lesson_mgr.reflection_open_text(self.reflection_engine, limit=limit)

    def reflection_history_text(self, limit: int = 10) -> str:
        return _lesson_mgr.reflection_history_text(self.reflection_engine, limit=limit)

    def reflection_answer(self, cycle_id: str, answer: str) -> str:
        return _lesson_mgr.reflection_answer(self.reflection_engine, self.bus, cycle_id, answer)

    def pending_actions_data(self, limit: int = 20) -> list[dict]:
        rows = self.reflection_engine.list_open(limit=500)
        out: list[dict] = []
        for row in rows:
            out.append(
                {
                    "id": row.get("id", ""),
                    "type": "reflection",
                    "lane": row.get("lane", "project"),
                    "project": row.get("project", self.project_slug),
                    "question": row.get("question_for_user", ""),
                    "summary": row.get("summary", ""),
                    "created_at": row.get("created_at", ""),
                }
            )
        web_rows = self.web_engine.list_pending(limit=500)
        for row in web_rows:
            out.append(
                {
                    "id": row.get("id", ""),
                    "type": "web_research",
                    "lane": row.get("lane", "research"),
                    "project": row.get("project", self.project_slug),
                    "question": "Live web research follow-up",
                    "summary": row.get("summary", ""),
                    "created_at": row.get("created_at", ""),
                }
            )
        try:
            for rev in self.topic_memory.list_pending_reviews():
                out.append({
                    "id": rev.get("id", ""),
                    "type": "topic_review",
                    "lane": "memory",
                    "project": rev.get("project", ""),
                    "question": rev.get("question", ""),
                    "summary": rev.get("claim", ""),
                    "confidence": rev.get("confidence", 0.0),
                    "topic_key": rev.get("topic_key", ""),
                    "created_at": rev.get("created_at", ""),
                })
        except Exception:
            pass
        try:
            if self.external_tools_settings.get_mode() != "off":
                for req in self.external_request_store.list_open(limit=500):
                    row = {
                        "id": req.get("id", ""),
                        "type": "external_request",
                        "lane": req.get("lane", "project"),
                        "project": req.get("project", self.project_slug),
                        "question": "External tool follow-up",
                        "summary": req.get("summary", ""),
                        "provider": req.get("provider", ""),
                        "intent": req.get("intent", ""),
                        "status": req.get("status", ""),
                        "created_at": req.get("created_at", ""),
                    }
                    suggestions_count = int(req.get("suggestions_count", 0) or 0)
                    if suggestions_count > 0:
                        row["suggestions_count"] = suggestions_count
                    out.append(row)
        except Exception:
            pass
        out.sort(key=lambda x: str(x.get("created_at", "")), reverse=True)
        return out[: max(1, min(limit, 500))]

    def pending_actions_text(self, limit: int = 20) -> str:
        actions = self.pending_actions_data(limit=limit)
        if not actions:
            return "No pending actions."
        lines = [f"Pending actions ({len(actions)}):"]
        for item in actions:
            lines.append(
                f"- {item.get('id','')} | type={item.get('type','')} | lane={item.get('lane','')} | "
                f"question={item.get('question','')}"
            )
        return "\n".join(lines)

    def ignore_pending_action(self, action_id: str, reason: str = "") -> str:
        if action_id.strip().lower().startswith("ext_"):
            try:
                row = self.external_request_store.mark_terminal(
                    action_id,
                    "ignored",
                    result_patch={
                        "ignored_reason": reason.strip() or "ignored by user",
                        "updated_at": datetime.now(timezone.utc).isoformat(),
                    },
                )
            except Exception:
                row = None
            if row is None:
                return f"Pending action not found or already resolved: {action_id}"
            self.bus.emit(
                "orchestrator",
                "pending_action_ignored",
                {"id": action_id, "type": "external_request", "reason": reason},
            )
            return f"Pending action ignored: {action_id}"

        if action_id.strip().lower().startswith("web_"):
            row = self.web_engine.ignore(request_id=action_id, reason=reason or "ignored by user")
            if row is None:
                return f"Pending action not found or already resolved: {action_id}"
            self.bus.emit(
                "orchestrator",
                "pending_action_ignored",
                {"id": action_id, "type": "web_research", "reason": reason},
            )
            return f"Pending action ignored: {action_id}"

        cycle = self.reflection_engine.ignore(cycle_id=action_id, reason=reason or "ignored by user")
        if cycle is None:
            return f"Pending action not found or already resolved: {action_id}"
        self.bus.emit(
            "orchestrator",
            "pending_action_ignored",
            {"id": action_id, "type": "reflection", "reason": reason},
        )
        return f"Pending action ignored: {action_id}"

    def send_pending_action_to_codex(self, action_id: str, note: str = "") -> str:
        if action_id.strip().lower().startswith("ext_"):
            return (
                "External request routing is not enabled in this phase. "
                "OpenClaw/CrewAI dispatch is intentionally gated off."
            )

        if action_id.strip().lower().startswith("web_"):
            request = self.web_engine.get_request(action_id)
            if request is None:
                return f"Pending action not found: {action_id}"
            if str(request.get("status", "")).lower() != "open":
                return f"Pending action is not open: {action_id}"
            request_text = (
                "Please perform web research with citations and links for this query.\n\n"
                f"Web Request ID: {action_id}\n"
                f"Project: {request.get('project', self.project_slug)}\n"
                f"Lane: {request.get('lane', 'research')}\n"
                f"Reason: {request.get('reason', '')}\n"
                f"Query: {request.get('query', '')}\n"
                "Return concise findings plus source URLs."
            )
            if note.strip():
                request_text += f"\nUser note: {note.strip()}\n"
            try:
                pending = self.handoff_queue.create_pending(
                    target="codex",
                    request_text=request_text,
                    project_slug=str(request.get("project", self.project_slug)),
                )
                approved = self.handoff_queue.approve(
                    request_id=str(pending.get("id", "")),
                    reason=f"routed from pending action {action_id}",
                    actor="orchestrator",
                )
            except (ValueError, PermissionError) as exc:
                return str(exc)
            routed = self.web_engine.mark_routed(
                action_id,
                target="codex",
                note=note,
                handoff_id=str(pending.get("id", "")),
            )
            if routed is None or approved is None:
                return f"Failed to route pending action {action_id} to Codex inbox."
            self.bus.emit(
                "orchestrator",
                "pending_action_routed_codex",
                {"id": action_id, "handoff_id": pending.get("id", ""), "type": "web_research"},
            )
            return (
                f"Pending action routed to Codex inbox.\n"
                f"Action: {action_id}\n"
                f"Handoff: {pending.get('id','')}\n"
                f"Inbox file: {approved.get('outbox_path','')}"
            )

        cycle = self.reflection_engine.get_cycle(action_id)
        if cycle is None:
            return f"Pending action not found: {action_id}"
        if str(cycle.get("status", "")).lower() != "open":
            return f"Pending action is not open: {action_id}"

        lane = str(cycle.get("lane", "project"))
        question = str(cycle.get("question_for_user", ""))
        summary = str(cycle.get("summary", ""))
        improvements = cycle.get("what_to_improve", [])
        if isinstance(improvements, list):
            improvements_text = "\n".join([f"- {str(x)}" for x in improvements if str(x).strip()])
        else:
            improvements_text = ""

        request_text = (
            "Please analyze and answer this reflection task with concrete corrective actions.\n\n"
            f"Reflection ID: {action_id}\n"
            f"Project: {cycle.get('project', self.project_slug)}\n"
            f"Lane: {lane}\n"
            f"Summary: {summary}\n"
            f"Question: {question}\n"
            "Known improvement areas:\n"
            f"{improvements_text or '- none listed'}\n"
        )
        if note.strip():
            request_text += f"\nUser note: {note.strip()}\n"

        try:
            pending = self.handoff_queue.create_pending(
                target="codex",
                request_text=request_text,
                project_slug=str(cycle.get("project", self.project_slug)),
            )
            approved = self.handoff_queue.approve(
                request_id=str(pending.get("id", "")),
                reason=f"routed from pending action {action_id}",
                actor="orchestrator",
            )
        except (ValueError, PermissionError) as exc:
            return str(exc)

        routed = self.reflection_engine.route_to_external(action_id, target="codex", note=note)
        if routed is None or approved is None:
            return f"Failed to route pending action {action_id} to Codex inbox."

        self.bus.emit(
            "orchestrator",
            "pending_action_routed_codex",
            {"id": action_id, "handoff_id": pending.get("id", "")},
        )
        return (
            f"Pending action routed to Codex inbox.\n"
            f"Action: {action_id}\n"
            f"Handoff: {pending.get('id','')}\n"
            f"Inbox file: {approved.get('outbox_path','')}"
        )

    def answer_pending_action(self, action_id: str, answer: str) -> str:
        if action_id.strip().lower().startswith("ext_"):
            note = answer.strip()
            if not note:
                return "Answer text is required."
            mode = self.external_tools_settings.get_mode()
            try:
                row = self.external_request_store.mark_terminal(
                    action_id,
                    "ignored",
                    result_patch={
                        "user_answer": note,
                        "dispatch_blocked": True,
                        "dispatch_blocked_reason": (
                            "OpenClaw/CrewAI provider wiring not enabled in this phase."
                        ),
                        "external_tools_mode": mode,
                        "updated_at": datetime.now(timezone.utc).isoformat(),
                    },
                )
            except Exception:
                row = None
            if row is None:
                return f"Pending action not found or already resolved: {action_id}"
            self.bus.emit(
                "orchestrator",
                "pending_action_ignored",
                {"id": action_id, "type": "external_request", "reason": note},
            )
            return f"Pending action ignored: {action_id}"

        if action_id.strip().lower().startswith("web_"):
            note = answer.strip()
            if not note:
                return "Answer text is required."
            low = note.lower()
            if low in {"no", "skip", "ignore", "deny", "not now"}:
                ignored = self.web_engine.ignore(action_id, reason=f"user answer: {note}")
                if ignored is None:
                    return f"Pending action not found or already resolved: {action_id}"
                self.bus.emit(
                    "orchestrator",
                    "pending_action_ignored",
                    {"id": action_id, "type": "web_research", "reason": note},
                )
                return f"Pending action ignored: {action_id}"

            result = self.web_engine.approve_and_run(action_id, note=note)
            if result is None:
                return f"Pending action not found or already resolved: {action_id}"
            if bool(result.get("ok", False)):
                feedback_text = self._web_learning_feedback(
                    str(result.get("query", "")),
                    result.get("sources", []),
                )
                learned = self.learning_engine.ingest_feedback_text(
                    feedback_text=feedback_text,
                    source="web_cache",
                    lane_hint="research",
                    project=str(result.get("project", self.project_slug)),
                    source_file=str(result.get("source_path", "web:pending")),
                    origin_type=ORIGIN_REFLECTION,
                )
                try:
                    _rep = DomainReputation(self.repo_root)
                    for _src in result.get("sources", []):
                        _domain = str(_src.get("source_domain", "") or _src.get("domain", "")).strip()
                        if _domain:
                            _rep.record_success(_domain)
                except Exception:
                    pass
                # Topic memory extraction (non-blocking)
                topic_result: dict[str, Any] = {}
                try:
                    model_cfg = lane_model_config(self.repo_root, "orchestrator_reasoning")
                    topic_result = self.topic_memory.extract_and_merge_from_research(
                        result,
                        ollama_client=self.ollama,
                        model_cfg=model_cfg,
                    )
                except Exception:
                    pass
                self.bus.emit(
                    "orchestrator",
                    "web_research_completed",
                    {
                        "id": action_id,
                        "project": result.get("project", self.project_slug),
                        "source_count": result.get("source_count", 0),
                        "conflict_count": int(
                            (result.get("conflict_summary", {}) or {}).get("conflict_count", 0)
                        ),
                        "source_path": result.get("source_path", ""),
                        "learned_lessons": learned.get("learned_lessons", 0),
                        "topic_canon_added": topic_result.get("canon_added", 0),
                        "topic_reviews_created": topic_result.get("reviews_created", 0),
                    },
                )
                topic_note = ""
                if topic_result.get("canon_added", 0) or topic_result.get("reviews_created", 0):
                    topic_note = (
                        f"\nTopic memory: {topic_result.get('canon_added', 0)} facts auto-canonized, "
                        f"{topic_result.get('reviews_created', 0)} pending review in Postbag."
                    )
                return (
                    f"Web research completed: {action_id}\n"
                    f"Sources captured: {result.get('source_count', 0)}\n"
                    f"Conflict flags: {int((result.get('conflict_summary', {}) or {}).get('conflict_count', 0))}\n"
                    f"Source cache file: {result.get('source_path', '')}\n"
                    f"Learned lessons from sources: {learned.get('learned_lessons', 0)}"
                    f"{topic_note}"
                )
            return f"Web research attempted but no sources captured: {action_id}"

        if action_id.strip().lower().startswith("rev_"):
            accepted = answer.strip().lower() not in {"no", "n", "reject", "wrong", "false", "skip"}
            ok = self.topic_memory.answer_review(action_id, accepted)
            if not ok:
                return f"Topic review not found or already answered: {action_id}"
            return "Memory updated — fact accepted." if accepted else "Memory updated — fact rejected."

        return self.reflection_answer(cycle_id=action_id, answer=answer)

    def replay_turn_text(self, turn_id: str, *, from_node: str = "", mutate_json: str = "") -> str:
        thread_id = str(turn_id or "").strip()
        if not thread_id:
            return "Usage: /replay <turn_id> [from=<node>] [mutate={...json...}]"
        mutate: dict[str, Any] = {}
        if mutate_json.strip():
            try:
                parsed = json.loads(mutate_json)
            except json.JSONDecodeError as exc:
                return f"Invalid mutate JSON: {exc}"
            if not isinstance(parsed, dict):
                return "Mutate payload must be a JSON object."
            mutate = parsed
        replay = replay_turn(
            self,
            thread_id=thread_id,
            from_node=from_node.strip(),
            mutate=mutate or None,
        )
        if not replay.get("ok"):
            return f"Replay failed: {replay.get('error', 'unknown error')}"
        trace = get_turn_trace(self.repo_root, thread_id=thread_id, orchestrator=self)
        turns = list_turns(self.repo_root, thread_id=thread_id)
        state = replay.get("state", {}) if isinstance(replay.get("state", {}), dict) else {}
        answer = str(state.get("composed_answer", "") or state.get("final_reply", "")).strip()
        lines = [
            f"Replay succeeded for thread `{thread_id}`.",
            f"Replay dir: {replay.get('replay_dir', '')}",
            f"Graph hash: {replay.get('graph_version_hash', '')}",
            f"Trace checkpoints: {len(trace)}",
            f"Thread snapshots found: {turns[0].checkpoints if turns else 0}",
        ]
        if answer:
            lines.append(f"Composed answer preview: {answer[:220]}")
        return "\\n".join(lines)

    def regression_text(self) -> str:
        report = run_regression_suite(self)
        if not bool(report.get("ok", False)):
            return str(report.get("error", "Regression suite failed."))
        total = int(report.get("total", 0) or 0)
        passed = int(report.get("passed", 0) or 0)
        failed = int(report.get("failed", 0) or 0)
        lines = [
            f"Regression suite complete: {passed}/{total} passed (threshold={float(report.get('threshold', 0.9)):.2f}).",
        ]
        failures = [row for row in (report.get("results") or []) if isinstance(row, dict) and not bool(row.get("passed", False))]
        for row in failures[:8]:
            lines.append(
                f"- {str(row.get('thread_id', ''))}: score={float(row.get('score', 0.0)):.3f} reason={str(row.get('reason', ''))}"
            )
        if failed > len(failures[:8]):
            lines.append(f"... and {failed - len(failures[:8])} more failures.")
        return "\\n".join(lines)


def print_help() -> None:
    print("Commands:")
    print("  [default text]    Foraging mode (unless explicit UI/product build intent)")
    print("  /project <slug>   Switch active project")
    print("  /status           Show runtime status")
    print("  /activity [n]     Show recent activity events")
    print("  /lanes [n]        Show lane usage for last n routed events")
    print("  /artifacts [n]    Show recent artifact paths")
    print("  /dashboard        Show status + lanes + artifacts")
    print("  /pending          List pending approvals")
    print("  /approve <id>     Approve pending action")
    print("  /reject <id>      Reject pending action")
    print("  /models           Show model routing config")
    print("  /local-models     Show pulled local Ollama models")
    print("  /reload-models    Reload model routing JSON")
    print("  /web-mode [off|ask|auto]  Show or set live web research mode")
    print("  /external-mode [off|ask|auto]  Show or set external tools mode")
    print("  /web-provider [auto|searxng|duckduckgo_html|duckduckgo_api]  Show or set web provider")
    print("  /web-sources [n]  Show recent cached web source runs for active project")
    print("  /project-facts    Show stored project facts memory")
    print("  /project-facts-clear  Clear stored project facts memory for active project")
    print("  /project-facts-refresh  Rebuild project facts from available user history")
    print("  /improve-status   Show continuous improvement health and quality stats")
    print("  /improve-now      Force immediate non-destructive project memory refresh")
    print("  /talk <text>      Send direct text to conversation layer")
    print("  /replay <turn_id> [from=<node>] [mutate={...json...}]  Replay a checkpointed turn")
    print("  /regression       Run replay regression suite from Runtime/state/regression_set.jsonl")
    print("  /ui <text>        Force UI/build intent for this message")
    print("  /handoff <target> <text>   Queue a pending handoff to codex")
    print("  /handoff-pending           List pending handoff requests")
    print("  /handoff-approve <id> [reason]   Approve pending handoff into inbox")
    print("  /handoff-deny <id> <reason>      Deny pending handoff with reason")
    print("  /handoff-inbox [target]          Show codex inbox summary")
    print("  /handoff-outbox [target] [n]     Show queued outbox files from codex")
    print("  /handoff-sync                    Auto-create missing outbox placeholders for inbox threads")
    print("  /handoff-monitor [n]             Show inbox/outbox monitor states per thread")
    print("  /learn-outbox <target> [lane] [n]  Ingest outbox feedback into learned lessons")
    print("  /learn-outbox-one <target> <thread_id> [lane]  Ingest one outbox thread response")
    print("  /lessons [lane] [n]              Show learned lessons")
    print("  /lesson-guidance [lane] [n]      Show active guidance injected into prompts")
    print("  /lesson-reinforce <id> <up|down> [note]  Reinforce or down-rank a lesson")
    print("  /lesson-expire <id>              Manually expire a lesson")
    print("  /reflect-open [n]                Show unanswered self-reflection questions")
    print("  /reflect-answer <id> <answer>    Answer and close a reflection cycle")
    print("  /reflect-history [n]             Show reflection cycle history")
    print("  /pending-actions [n]             Show pending actions board")
    print("  /action-ignore <id> [reason]     Ignore pending action")
    print("  /action-codex <id> [note]        Route pending action to Codex inbox")
    print("  /action-answer <id> <answer>     Answer pending action directly")
    print("  /help             Show commands")
    print("  exit              Quit")


def parse_optional_int(command: str, default: int, minimum: int = 1, maximum: int = 500) -> int:
    parts = command.split()
    if len(parts) < 2:
        return default
    try:
        value = int(parts[1])
    except ValueError:
        return default
    return max(minimum, min(maximum, value))


def main() -> None:
    orch = OathweaverOrchestrator(ROOT)

    print("Oathweaver Orchestrator")
    print("Type /help for commands. Type exit to quit.")

    while True:
        try:
            user_text = input("You> ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nExiting.")
            break

        if not user_text:
            continue
        if user_text.lower() in {"exit", "quit"}:
            print("Exiting.")
            break
        if user_text == "/help":
            print_help()
            continue
        if user_text.startswith("/project "):
            print(orch.set_project(user_text[len("/project ") :]))
            continue
        if user_text == "/status":
            print(orch.status_text())
            continue
        if user_text.startswith("/activity"):
            print(orch.activity_text(limit=parse_optional_int(user_text, default=20)))
            continue
        if user_text.startswith("/lanes"):
            print(orch.lanes_text(window=parse_optional_int(user_text, default=200)))
            continue
        if user_text.startswith("/artifacts"):
            print(orch.artifacts_text(limit=parse_optional_int(user_text, default=20)))
            continue
        if user_text == "/dashboard":
            print(orch.status_text())
            print(orch.lanes_text(window=200))
            print(orch.artifacts_text(limit=20))
            continue
        if user_text == "/pending":
            print(orch.pending_approvals_text())
            continue
        if user_text.startswith("/approve "):
            print(orch.decide_approval(user_text[len("/approve ") :].strip(), True))
            continue
        if user_text.startswith("/reject "):
            print(orch.decide_approval(user_text[len("/reject ") :].strip(), False))
            continue
        if user_text == "/models":
            print(orch.models_text())
            continue
        if user_text == "/local-models":
            print(orch.local_models_text())
            continue
        if user_text == "/reload-models":
            print(orch.reload_models())
            continue
        if user_text.startswith("/web-mode"):
            parts = user_text.split()
            if len(parts) == 1:
                print(orch.web_mode_text())
            else:
                print(orch.set_web_mode(parts[1].strip()))
            continue
        if user_text.startswith("/external-mode"):
            parts = user_text.split()
            if len(parts) == 1:
                print(orch.external_tools_mode_text())
            else:
                print(orch.set_external_tools_mode(parts[1].strip()))
            continue
        if user_text.startswith("/web-provider"):
            parts = user_text.split()
            if len(parts) == 1:
                print(orch.web_mode_text())
            else:
                print(orch.set_web_provider(parts[1].strip()))
            continue
        if user_text.startswith("/web-sources"):
            limit = parse_optional_int(user_text, default=10, minimum=1, maximum=100)
            print(orch.web_sources_text(limit=limit))
            continue
        if user_text == "/project-facts":
            print(orch.project_facts_text())
            continue
        if user_text == "/project-facts-clear":
            print(orch.clear_project_facts())
            continue
        if user_text == "/project-facts-refresh":
            print(orch.refresh_project_facts(history=None, reset=False))
            continue
        if user_text == "/improve-status":
            print(orch.improvement_status_text())
            continue
        if user_text == "/improve-now":
            print(
                orch.improvement_run_now(
                    history=None,
                )
            )
            continue
        if user_text == "/handoff-pending":
            print(orch.handoff_pending_text())
            continue
        if user_text.startswith("/handoff-approve "):
            parts = user_text.split(maxsplit=2)
            request_id = parts[1].strip() if len(parts) > 1 else ""
            reason = parts[2].strip() if len(parts) > 2 else ""
            print(orch.approve_handoff(request_id=request_id, reason=reason))
            continue
        if user_text.startswith("/handoff-deny "):
            parts = user_text.split(maxsplit=2)
            if len(parts) < 3:
                print("Usage: /handoff-deny <id> <reason>")
                continue
            request_id = parts[1].strip()
            reason = parts[2].strip()
            print(orch.deny_handoff(request_id=request_id, reason=reason))
            continue
        if user_text.startswith("/handoff-inbox"):
            parts = user_text.split(maxsplit=1)
            target = parts[1].strip() if len(parts) > 1 else None
            print(orch.handoff_inbox_text(target=target))
            continue
        if user_text.startswith("/handoff-outbox"):
            parts = user_text.split()
            target = parts[1].strip().lower() if len(parts) > 1 and not parts[1].isdigit() else None
            number_arg = next((p for p in parts[1:] if p.isdigit()), None)
            limit = int(number_arg) if number_arg else 20
            print(orch.handoff_outbox_text(target=target, limit=limit))
            continue
        if user_text == "/handoff-sync":
            print(orch.handoff_sync())
            continue
        if user_text.startswith("/handoff-monitor"):
            limit = parse_optional_int(user_text, default=50, minimum=1, maximum=500)
            print(orch.handoff_monitor_text(limit=limit))
            continue
        if user_text.startswith("/handoff "):
            parts = user_text.split(maxsplit=2)
            if len(parts) < 3:
                print("Usage: /handoff <codex> <request text>")
                continue
            target = parts[1].strip().lower()
            request_text = parts[2].strip()
            print(orch.create_handoff(target=target, request_text=request_text))
            continue
        if user_text.startswith("/learn-outbox "):
            parts = user_text.split()
            if len(parts) < 2:
                print("Usage: /learn-outbox <codex> [lane] [n]")
                continue
            target = parts[1].strip().lower()
            lane_hint = None
            limit = 5
            for token in parts[2:]:
                if token.isdigit():
                    limit = int(token)
                else:
                    lane_hint = token.strip().lower()
            print(orch.learn_outbox(target=target, lane_hint=lane_hint, limit=limit))
            continue
        if user_text.startswith("/learn-outbox-one "):
            parts = user_text.split()
            if len(parts) < 3:
                print("Usage: /learn-outbox-one <codex> <thread_id> [lane]")
                continue
            target = parts[1].strip().lower()
            thread_id = parts[2].strip()
            lane_hint = parts[3].strip().lower() if len(parts) > 3 else None
            result = orch.learn_outbox_one(target=target, thread_id=thread_id, lane_hint=lane_hint)
            print(result.get("message", "Outbox one-thread ingest complete."))
            print(f"Lesson IDs: {', '.join(result.get('lesson_ids', [])[:8]) or 'none'}")
            continue
        if user_text.startswith("/lessons"):
            parts = user_text.split()
            lane = None
            limit = 10
            for token in parts[1:]:
                if token.isdigit():
                    limit = int(token)
                else:
                    lane = token.strip().lower()
            print(orch.lessons_text(lane=lane, limit=limit))
            continue
        if user_text.startswith("/lesson-guidance"):
            parts = user_text.split()
            lane = None
            limit = 5
            for token in parts[1:]:
                if token.isdigit():
                    limit = int(token)
                else:
                    lane = token.strip().lower()
            print(orch.lesson_guidance_text(lane=lane, limit=limit))
            continue
        if user_text.startswith("/lesson-reinforce "):
            parts = user_text.split(maxsplit=3)
            if len(parts) < 3:
                print("Usage: /lesson-reinforce <id> <up|down> [note]")
                continue
            lesson_id = parts[1].strip()
            direction = parts[2].strip().lower()
            note = parts[3].strip() if len(parts) > 3 else ""
            print(orch.lesson_reinforce(lesson_id=lesson_id, direction=direction, note=note))
            continue
        if user_text.startswith("/lesson-expire "):
            lesson_id = user_text[len("/lesson-expire "):].strip()
            if not lesson_id:
                print("Usage: /lesson-expire <id>")
            else:
                print(orch.lesson_expire(lesson_id))
            continue
        if user_text.startswith("/reflect-open"):
            parts = user_text.split()
            limit = int(parts[1]) if len(parts) > 1 and parts[1].isdigit() else 10
            print(orch.reflection_open_text(limit=limit))
            continue
        if user_text.startswith("/reflect-history"):
            parts = user_text.split()
            limit = int(parts[1]) if len(parts) > 1 and parts[1].isdigit() else 10
            print(orch.reflection_history_text(limit=limit))
            continue
        if user_text.startswith("/reflect-answer "):
            parts = user_text.split(maxsplit=2)
            if len(parts) < 3:
                print("Usage: /reflect-answer <id> <answer>")
                continue
            cycle_id = parts[1].strip()
            answer = parts[2].strip()
            print(orch.reflection_answer(cycle_id=cycle_id, answer=answer))
            continue
        if user_text.startswith("/pending-actions"):
            parts = user_text.split()
            limit = int(parts[1]) if len(parts) > 1 and parts[1].isdigit() else 20
            print(orch.pending_actions_text(limit=limit))
            continue
        if user_text.startswith("/action-ignore "):
            parts = user_text.split(maxsplit=2)
            if len(parts) < 2:
                print("Usage: /action-ignore <id> [reason]")
                continue
            action_id = parts[1].strip()
            reason = parts[2].strip() if len(parts) > 2 else ""
            print(orch.ignore_pending_action(action_id=action_id, reason=reason))
            continue
        if user_text.startswith("/action-codex "):
            parts = user_text.split(maxsplit=2)
            if len(parts) < 2:
                print("Usage: /action-codex <id> [note]")
                continue
            action_id = parts[1].strip()
            note = parts[2].strip() if len(parts) > 2 else ""
            print(orch.send_pending_action_to_codex(action_id=action_id, note=note))
            continue
        if user_text.startswith("/action-answer "):
            parts = user_text.split(maxsplit=2)
            if len(parts) < 3:
                print("Usage: /action-answer <id> <answer>")
                continue
            action_id = parts[1].strip()
            answer = parts[2].strip()
            print(orch.answer_pending_action(action_id=action_id, answer=answer))
            continue
        if user_text.startswith("/replay"):
            parts = user_text.split(maxsplit=1)
            args = parts[1].strip() if len(parts) > 1 else ""
            if not args:
                print("Usage: /replay <turn_id> [from=<node>] [mutate={...json...}]")
                continue
            mutate_json = ""
            mutate_pos = args.find("mutate=")
            if mutate_pos >= 0:
                mutate_json = args[mutate_pos + len("mutate="):].strip()
                args = args[:mutate_pos].strip()
            turn_id = args.split()[0] if args else ""
            from_node = ""
            for token in args.split()[1:]:
                if token.startswith("from="):
                    from_node = token[len("from="):].strip()
            print(orch.replay_turn_text(turn_id, from_node=from_node, mutate_json=mutate_json))
            continue
        if user_text == "/regression":
            print(orch.regression_text())
            continue
        if user_text.startswith("/talk "):
            print(f"Conversation> {orch.conversation_reply(user_text[len('/talk ') :].strip())}")
            continue

        reply = orch.handle_message(user_text)
        print(f"Orchestrator> {reply}")


if __name__ == "__main__":
    main()
