from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Any, Callable

from shared_tools.hardware_profiles import hardware_profile_summary, hardware_profile_to_router_policy

_OWNER_ROLES = {"owner", "admin"}
_HEALTH_TTL_SEC = 30.0
_EXPLAIN_TTL_SEC = 300.0
_HARDWARE_TTL_SEC = 600.0


def _safe_float(value: Any) -> float:
    try:
        return float(value)
    except Exception:
        return 0.0


def _safe_int(value: Any) -> int:
    try:
        return int(value)
    except Exception:
        return 0


@dataclass(frozen=True)
class SelfState:
    chat_layer_model: str
    chat_layer_backend: str
    chat_layer_context_window: int
    chat_layer_fallback_chain: list[str]
    chat_layer_size_b: float
    chat_layer_weight_class: str
    chat_layer_reasoning: bool
    backends: list[dict[str, Any]]
    loaded_models: list[str]
    vram_used_gb: float
    vram_capacity_gb: float
    kv_pressure: float
    hardware_profile_name: str
    hardware_profile_display_name: str
    hardware_profile_gpu_backend: str
    hardware_profile_gpu_vram_gb: float
    hardware_profile_max_context_tokens: int
    hardware_profile_allow_premium: bool
    validation_warnings: list[str]
    validation_errors: list[str]
    project: str
    cag_row_count: int
    recent_claims: list[dict[str, Any]]
    role_scope: str
    redacted_fields: list[str]
    cached_at: float

    def top_values(self, match_kind: str) -> list[str]:
        kind = str(match_kind or "").strip().lower() or "general"
        if kind == "model":
            return [self.chat_layer_model]
        if kind == "hardware":
            return [self.hardware_profile_name, self.hardware_profile_gpu_backend]
        if kind == "backend":
            for backend in self.backends:
                if bool(backend.get("reachable", False)):
                    return [str(backend.get("name", "")).strip()]
            return []
        if kind == "loaded":
            return [self.loaded_models[0]] if self.loaded_models else []
        return [self.chat_layer_model, self.hardware_profile_name]

    def to_prompt_block(self, match_kind: str = "general") -> str:
        kind = str(match_kind or "").strip().lower() or "general"
        age_sec = max(0, int(round(time.time() - float(self.cached_at or 0.0))))
        lines = [f"[oathweaver self_state - authoritative current values, snapshot at t={age_sec}s ago]"]

        def add(line: str) -> None:
            if str(line).strip():
                lines.append(line)

        include_backends = kind in {"backend", "general"}
        include_loaded = kind in {"model", "loaded", "general"}
        include_routing = kind in {"model", "routing", "general"}
        include_hardware = kind in {"hardware", "capability", "general"}
        include_capability = kind in {"capability", "general"}
        include_validation = kind == "general"
        include_claims = kind in {"routing", "capability", "general"}

        if include_routing or include_capability:
            add(f"chat_layer.model: {self.chat_layer_model}")
            add(f"chat_layer.backend: {self.chat_layer_backend}")
            add(f"chat_layer.context_window: {self.chat_layer_context_window}")
            add(f"chat_layer.weight_class: {self.chat_layer_weight_class}")
            add(f"chat_layer.size_b: {self.chat_layer_size_b}")
            add(f"chat_layer.fallback_chain: {self.chat_layer_fallback_chain}")

        if include_backends:
            for backend in self.backends:
                name = str(backend.get("name", "")).strip() or "unknown"
                reachable = "reachable" if bool(backend.get("reachable", False)) else "unreachable"
                model_count = len(backend.get("models", []) or [])
                add(f"backends.{name}: {reachable} ({model_count} models)")

        if include_loaded:
            add(f"loaded_models: {self.loaded_models}")
            add(f"vram_used_gb: {self.vram_used_gb}")
            add(f"vram_capacity_gb: {self.vram_capacity_gb}")
            add(f"kv_pressure: {self.kv_pressure}")

        if include_hardware:
            add(f"hardware_profile.name: {self.hardware_profile_name}")
            add(f"hardware_profile.display_name: {self.hardware_profile_display_name}")
            add(f"hardware_profile.gpu_backend: {self.hardware_profile_gpu_backend}")
            add(f"hardware_profile.gpu_vram_gb: {self.hardware_profile_gpu_vram_gb}")
            add(f"hardware_profile.max_context_tokens: {self.hardware_profile_max_context_tokens}")
            add(f"hardware_profile.allow_premium: {self.hardware_profile_allow_premium}")

        if include_validation:
            if self.validation_warnings:
                add(f"validation.warnings: {len(self.validation_warnings)} ({'; '.join(self.validation_warnings[:3])})")
            if self.validation_errors:
                add(f"validation.errors: {len(self.validation_errors)} ({'; '.join(self.validation_errors[:3])})")
            if self.project:
                add(f"project: {self.project}")
            if self.cag_row_count > 0:
                add(f"cag_row_count: {self.cag_row_count}")

        if include_claims and self.recent_claims:
            add("recent_claims:")
            for row in self.recent_claims[:2]:
                created = str(row.get("created_at", "")).strip()[:10]
                claim = str(row.get("claim", "")).strip()
                if claim:
                    add(f"  - {created}: \"{claim}\"")

        add("")
        add("When asked about configuration/model/backends/hardware/current state, quote values from this block exactly.")
        add("If a relevant value is missing, say \"I don't have that information available\".")
        return "\n".join(lines)


class SelfStateService:
    def __init__(
        self,
        *,
        router: Any,
        capability_registry: Any,
        cag_store: Any,
        hardware_profile_provider: Callable[[], dict[str, Any]],
        project_slug_provider: Callable[[], str],
    ) -> None:
        self.router = router
        self.capability_registry = capability_registry
        self.cag_store = cag_store
        self.hardware_profile_provider = hardware_profile_provider
        self.project_slug_provider = project_slug_provider
        self._health_cache: dict[str, Any] = {"ts": 0.0, "health": {}, "memory": {}}
        self._explain_cache: dict[str, Any] = {"ts": 0.0, "explain": {}}
        self._hardware_cache: dict[str, Any] = {"ts": 0.0, "summary": {}, "validation": {}}

    def _health(self) -> tuple[dict[str, Any], dict[str, Any], float]:
        now = time.time()
        if now - float(self._health_cache.get("ts", 0.0)) <= _HEALTH_TTL_SEC:
            return (
                dict(self._health_cache.get("health", {}) or {}),
                dict(self._health_cache.get("memory", {}) or {}),
                float(self._health_cache.get("ts", now)),
            )
        health: dict[str, Any]
        memory: dict[str, Any]
        try:
            health = self.router.health_report()
            health = health if isinstance(health, dict) else {}
        except Exception:
            health = {}
        try:
            memory = self.router.memory_state()
            memory = memory if isinstance(memory, dict) else {}
        except Exception:
            memory = {}
        self._health_cache = {"ts": now, "health": health, "memory": memory}
        return health, memory, now

    def _explain(self) -> tuple[dict[str, Any], float]:
        now = time.time()
        if now - float(self._explain_cache.get("ts", 0.0)) <= _EXPLAIN_TTL_SEC:
            return dict(self._explain_cache.get("explain", {}) or {}), float(self._explain_cache.get("ts", now))
        try:
            explain = self.router.explain_route(task_class="chat_layer")
            explain = explain if isinstance(explain, dict) else {}
        except Exception:
            explain = {}
        self._explain_cache = {"ts": now, "explain": explain}
        return explain, now

    def _hardware(self) -> tuple[dict[str, Any], dict[str, Any], float]:
        now = time.time()
        if now - float(self._hardware_cache.get("ts", 0.0)) <= _HARDWARE_TTL_SEC:
            return (
                dict(self._hardware_cache.get("summary", {}) or {}),
                dict(self._hardware_cache.get("validation", {}) or {}),
                float(self._hardware_cache.get("ts", now)),
            )
        profile = self.hardware_profile_provider() or {}
        try:
            summary = hardware_profile_summary(profile)
            summary = summary if isinstance(summary, dict) else {}
        except Exception:
            summary = {}
        try:
            validation = self.router.validate_config(profile=hardware_profile_to_router_policy(profile))
            validation = validation if isinstance(validation, dict) else {}
        except Exception:
            validation = {}
        if isinstance(summary.get("resolution_warnings"), list):
            merged = list(validation.get("warnings", []) or [])
            for row in summary.get("resolution_warnings", []):
                text = str(row).strip()
                if text and text not in merged:
                    merged.append(text)
            validation["warnings"] = merged
        self._hardware_cache = {"ts": now, "summary": summary, "validation": validation}
        return summary, validation, now

    def compute(self, match_kind: str, *, role: str = "owner") -> SelfState:
        explain, explain_ts = self._explain()
        health, memory, health_ts = self._health()
        hardware, validation, hardware_ts = self._hardware()
        cached_at = min(explain_ts, health_ts, hardware_ts)

        model = str(explain.get("selected_model") or explain.get("requested_model") or "").strip()
        if not model:
            model = str(explain.get("model", "")).strip()
        backend = str(explain.get("backend", "")).strip()
        fallback_chain = [str(x).strip() for x in (explain.get("fallback_chain") or []) if str(x).strip()]
        context_window = _safe_int(self.router.context_window(model)) if model else 0
        try:
            caps = self.router.capabilities(model) if model else {}
        except Exception:
            caps = {}
        caps = caps if isinstance(caps, dict) else {}

        backends = health.get("backends") if isinstance(health.get("backends"), list) else []
        loaded_models = [str(x).strip() for x in (memory.get("loaded_models") or []) if str(x).strip()]
        recent_claims = []
        try:
            recent_claims = self.capability_registry.list_recent_claims(limit=5)
        except Exception:
            try:
                claims = self.capability_registry.list_claims()
                claims = claims if isinstance(claims, list) else []
                recent_claims = [
                    {
                        "id": str(row.get("id", "")),
                        "created_at": str(row.get("updated_at") or row.get("created_at") or ""),
                        "claim": str(row.get("claim", "")),
                        "evidence_summary": ", ".join(str(x) for x in (row.get("benchmarks") or []) if str(x).strip()),
                    }
                    for row in claims[:5]
                    if isinstance(row, dict)
                ]
            except Exception:
                recent_claims = []

        project_slug = str(self.project_slug_provider() or "").strip() or "general"
        cag_row_count = 0
        try:
            cag_row_count = _safe_int(self.cag_store.count_rows(project=project_slug))
        except Exception:
            cag_row_count = 0

        row = SelfState(
            chat_layer_model=model,
            chat_layer_backend=backend,
            chat_layer_context_window=context_window,
            chat_layer_fallback_chain=fallback_chain,
            chat_layer_size_b=_safe_float(caps.get("size_b")),
            chat_layer_weight_class=str(caps.get("weight_class", "")).strip(),
            chat_layer_reasoning=bool(caps.get("reasoning", False)),
            backends=[dict(x) for x in backends if isinstance(x, dict)],
            loaded_models=loaded_models,
            vram_used_gb=_safe_float(memory.get("vram_used_gb")),
            vram_capacity_gb=_safe_float(memory.get("vram_capacity_gb")),
            kv_pressure=_safe_float(memory.get("kv_pressure")),
            hardware_profile_name=str(hardware.get("name", "")).strip(),
            hardware_profile_display_name=str(hardware.get("display_name", "")).strip(),
            hardware_profile_gpu_backend=str((hardware.get("hardware") or {}).get("gpu_backend", "")).strip(),
            hardware_profile_gpu_vram_gb=_safe_float((hardware.get("hardware") or {}).get("gpu_vram_gb")),
            hardware_profile_max_context_tokens=_safe_int((hardware.get("scheduler") or {}).get("max_context_tokens")),
            hardware_profile_allow_premium=bool((hardware.get("model_policy") or {}).get("allow_premium", False)),
            validation_warnings=[str(x).strip() for x in (validation.get("warnings") or []) if str(x).strip()],
            validation_errors=[str(x).strip() for x in (validation.get("errors") or []) if str(x).strip()],
            project=project_slug,
            cag_row_count=cag_row_count,
            recent_claims=[dict(x) for x in recent_claims if isinstance(x, dict)],
            role_scope=str(role or "owner").strip().lower() or "owner",
            redacted_fields=[],
            cached_at=float(cached_at),
        )
        return self._apply_role_redaction(row, match_kind=match_kind)

    def _apply_role_redaction(self, row: SelfState, *, match_kind: str) -> SelfState:
        role = str(row.role_scope or "").strip().lower() or "owner"
        if role in _OWNER_ROLES:
            return row
        redactions = [
            "backends",
            "loaded_models",
            "vram_used_gb",
            "vram_capacity_gb",
            "kv_pressure",
            "hardware_profile_name",
            "hardware_profile_gpu_backend",
            "hardware_profile_gpu_vram_gb",
            "hardware_profile_allow_premium",
            "validation_warnings",
            "validation_errors",
            "project",
            "cag_row_count",
            "recent_claims",
        ]
        return SelfState(
            chat_layer_model=row.chat_layer_model,
            chat_layer_backend="",
            chat_layer_context_window=row.chat_layer_context_window,
            chat_layer_fallback_chain=[],
            chat_layer_size_b=0.0,
            chat_layer_weight_class="",
            chat_layer_reasoning=False,
            backends=[],
            loaded_models=[],
            vram_used_gb=0.0,
            vram_capacity_gb=0.0,
            kv_pressure=0.0,
            hardware_profile_name="",
            hardware_profile_display_name=row.hardware_profile_display_name,
            hardware_profile_gpu_backend="",
            hardware_profile_gpu_vram_gb=0.0,
            hardware_profile_max_context_tokens=0,
            hardware_profile_allow_premium=False,
            validation_warnings=[],
            validation_errors=[],
            project="",
            cag_row_count=0,
            recent_claims=[],
            role_scope=role,
            redacted_fields=redactions,
            cached_at=row.cached_at,
        )
