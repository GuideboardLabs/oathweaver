"""Inference router that dispatches model calls to Ollama or llama.cpp servers.

Drop-in replacement for OllamaClient — same .chat() / .embed() / .list_local_models() API.
When ``llama_cpp_servers`` is configured in model_routing.json, matching models are routed
to a TurboQuant-enabled llama.cpp server; everything else goes through Ollama as usual.
"""

from __future__ import annotations

import hashlib
import json
import logging
import re
import threading
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

from shared_tools.hardware_profiles import active_router_policy_from_env, hardware_profile_to_router_policy
from shared_tools.llamacpp_client import LlamaCppClient
from shared_tools.model_routing import load_model_routing
from shared_tools.ollama_client import OllamaClient

LOGGER = logging.getLogger(__name__)

_MODEL_SIZE_RE = re.compile(r"(?<![a-z0-9])([0-9]+(?:\.[0-9]+)?)\s*b(?![a-z])", flags=re.IGNORECASE)
_SIZE_RE = re.compile(r"^\s*([0-9]+(?:\.[0-9]+)?)\s*([kmgt]?i?b)?\s*$", flags=re.IGNORECASE)


def _to_gb(raw: Any) -> float:
    if raw is None:
        return 0.0
    if isinstance(raw, (int, float)):
        val = float(raw)
        if val > 1024.0:
            return val / (1024.0 ** 3)
        return val
    text = str(raw).strip()
    if not text:
        return 0.0
    match = _SIZE_RE.match(text)
    if not match:
        return 0.0
    number = float(match.group(1))
    unit = str(match.group(2) or "gb").lower()
    if unit == "b":
        return number / (1024.0 ** 3)
    if unit in {"kb", "kib"}:
        return number / (1024.0 ** 2)
    if unit in {"mb", "mib"}:
        return number / 1024.0
    if unit in {"tb", "tib"}:
        return number * 1024.0
    return number


class InferenceRouter:
    _SERVER_BACKOFF_SEC = 180.0
    _SERVER_MODELS_TTL_SEC = 300.0
    _shared_lock = threading.Lock()
    _shared_backoff_until: dict[str, float] = {}
    _shared_models_cache: dict[str, dict[str, Any]] = {}
    _shared_response_cache: dict[str, dict[str, Any]] = {}
    _shared_response_cache_lock = threading.Lock()
    _MAX_RESPONSE_CACHE_ENTRIES = 300
    _FALLBACK_KEYS = ("fallback_models", "synthesis_fallback_models")

    def __init__(self, repo_root: Path | None = None) -> None:
        self._ollama = OllamaClient()
        self._llama_clients: dict[str, LlamaCppClient] = {}
        self._model_map: dict[str, str] = {}  # model_name -> server_key
        self._fallback_flags: dict[str, bool] = {}  # server_key -> fallback_to_ollama
        self.last_wait_error = ""
        self.last_wait_candidates: list[str] = []
        self.last_wait_polls = 0
        self.last_wait_elapsed_sec = 0

        if repo_root is None:
            repo_root = Path(__file__).resolve().parents[2]
        self.repo_root = Path(repo_root)

        self._routing = load_model_routing(self.repo_root)
        servers = self._routing.get("llama_cpp_servers")
        if not isinstance(servers, dict):
            servers = {}

        for key, cfg in servers.items():
            if not isinstance(cfg, dict):
                continue
            base_url = str(cfg.get("base_url", "")).strip()
            if not base_url:
                continue
            models = cfg.get("models", [])
            if not isinstance(models, list):
                continue
            self._llama_clients[key] = LlamaCppClient(base_url)
            self._fallback_flags[key] = bool(cfg.get("fallback_to_ollama", True))
            for model_name in models:
                name = str(model_name).strip()
                if name:
                    self._model_map[name] = key

        if self._model_map:
            LOGGER.info("InferenceRouter: llama.cpp routing active for %s", list(self._model_map.keys()))

    def _client_for_model(self, model: str) -> OllamaClient | LlamaCppClient:
        server_key = self._model_map.get(model)
        if server_key and server_key in self._llama_clients:
            return self._llama_clients[server_key]
        return self._ollama

    @classmethod
    def _server_in_backoff(cls, server_key: str) -> bool:
        now = time.monotonic()
        with cls._shared_lock:
            until = float(cls._shared_backoff_until.get(server_key, 0.0) or 0.0)
        return until > now

    @classmethod
    def _mark_server_backoff(cls, server_key: str, seconds: float | None = None) -> None:
        duration = float(seconds if seconds is not None else cls._SERVER_BACKOFF_SEC)
        with cls._shared_lock:
            cls._shared_backoff_until[server_key] = time.monotonic() + max(5.0, duration)

    @classmethod
    def _clear_server_backoff(cls, server_key: str) -> None:
        with cls._shared_lock:
            cls._shared_backoff_until.pop(server_key, None)

    @classmethod
    def _server_backoff_remaining_sec(cls, server_key: str) -> int:
        now = time.monotonic()
        with cls._shared_lock:
            until = float(cls._shared_backoff_until.get(server_key, 0.0) or 0.0)
        return int(max(0.0, round(until - now)))

    def _server_declares_model(self, model: str) -> bool:
        server_key = self._model_map.get(model, "")
        if not server_key or server_key not in self._llama_clients:
            return False
        if self._server_in_backoff(server_key):
            return False

        now = time.monotonic()
        with self._shared_lock:
            cached = dict(self._shared_models_cache.get(server_key) or {})
        expires_at = float(cached.get("expires_at", 0.0) or 0.0)
        models = cached.get("models")
        if expires_at > now and isinstance(models, set):
            return model in models

        client = self._llama_clients[server_key]
        try:
            declared = set(client.list_local_models_strict())
        except Exception as exc:
            LOGGER.warning("InferenceRouter: llama.cpp model discovery failed for %s: %s", server_key, exc)
            self._mark_server_backoff(server_key)
            return False

        with self._shared_lock:
            self._shared_models_cache[server_key] = {
                "expires_at": now + self._SERVER_MODELS_TTL_SEC,
                "models": declared,
            }
        self._clear_server_backoff(server_key)
        return model in declared

    def _should_fallback(self, model: str) -> bool:
        server_key = self._model_map.get(model, "")
        return self._fallback_flags.get(server_key, False)

    @staticmethod
    def _candidate_models(model: str, fallback_models: list[str] | None = None) -> list[str]:
        out: list[str] = []
        for name in [model, *(fallback_models or [])]:
            key = str(name or "").strip()
            if not key or key in out:
                continue
            out.append(key)
        return out

    @staticmethod
    def _cache_ttl_for_call(*, task_class: str, temperature: float, think: bool | None) -> int:
        task = str(task_class or "").strip().lower()
        if task in {"intent", "routing", "classifier"}:
            return 900
        if task in {"contract", "contract_retry", "planner", "critic", "reflection"}:
            return 300
        if think:
            return 0
        if float(temperature or 0.0) <= 0.15:
            return 120
        return 0

    @staticmethod
    def _response_cache_key(
        *,
        model: str,
        system_prompt: str,
        user_prompt: str,
        prior_messages: list[dict[str, str]] | None,
        user_images: list[str] | None,
        temperature: float,
        num_ctx: int,
        think: bool | None,
        num_predict: int | None,
        task_class: str,
    ) -> str:
        base_payload = {
            "model": str(model or ""),
            "system_prompt_hash": hashlib.sha256(str(system_prompt or "").encode("utf-8")).hexdigest(),
            "user_prompt_hash": hashlib.sha256(str(user_prompt or "").encode("utf-8")).hexdigest(),
            "temperature": float(temperature or 0.0),
            "num_ctx": int(num_ctx or 0),
            "task_class": str(task_class or "").strip().lower(),
        }
        base_raw = json.dumps(base_payload, sort_keys=True, ensure_ascii=True)
        base_key = hashlib.sha256(base_raw.encode("utf-8")).hexdigest()
        extras_needed = bool(prior_messages) or bool(user_images) or think is not None or int(num_predict if num_predict is not None else -1) != -1
        if not extras_needed:
            return base_key
        extra_payload = {
            "prior_messages": prior_messages or [],
            "user_images": user_images or [],
            "think": bool(think) if think is not None else None,
            "num_predict": int(num_predict if num_predict is not None else -1),
        }
        extra_raw = json.dumps(extra_payload, sort_keys=True, ensure_ascii=True)
        return f"{base_key}:{hashlib.sha256(extra_raw.encode('utf-8')).hexdigest()}"

    @classmethod
    def _cache_get(cls, key: str) -> str | None:
        now = time.monotonic()
        with cls._shared_response_cache_lock:
            row = cls._shared_response_cache.get(key)
            if not isinstance(row, dict):
                return None
            expires_at = float(row.get("expires_at", 0.0) or 0.0)
            if expires_at <= now:
                cls._shared_response_cache.pop(key, None)
                return None
            value = str(row.get("value", ""))
            if not value:
                return None
            row["last_access_at"] = now
            return value

    @classmethod
    def _cache_put(cls, key: str, value: str, ttl_sec: int) -> None:
        if ttl_sec <= 0:
            return
        now = time.monotonic()
        with cls._shared_response_cache_lock:
            cls._shared_response_cache[key] = {
                "value": str(value or ""),
                "created_at": now,
                "last_access_at": now,
                "expires_at": now + max(1, int(ttl_sec)),
            }
            if len(cls._shared_response_cache) <= cls._MAX_RESPONSE_CACHE_ENTRIES:
                return
            # Evict oldest access first to keep cache bounded.
            ordered = sorted(
                cls._shared_response_cache.items(),
                key=lambda item: float((item[1] or {}).get("last_access_at", 0.0)),
            )
            overflow = len(cls._shared_response_cache) - cls._MAX_RESPONSE_CACHE_ENTRIES
            for idx in range(max(0, overflow)):
                cls._shared_response_cache.pop(ordered[idx][0], None)

    @staticmethod
    def _clean_model_list(value: Any) -> list[str]:
        if not isinstance(value, list):
            return []
        out: list[str] = []
        for item in value:
            name = str(item or "").strip()
            if name and name not in out:
                out.append(name)
        return out

    @staticmethod
    def _append_unique(items: list[str], value: str) -> None:
        name = str(value or "").strip()
        if name and name not in items:
            items.append(name)

    @classmethod
    def _iter_route_configs(cls, value: Any, path: str = ""):
        if isinstance(value, dict):
            has_model_config = "model" in value or any(key in value for key in cls._FALLBACK_KEYS)
            if has_model_config:
                yield path or "<root>", value
            for key, child in value.items():
                child_path = f"{path}.{key}" if path else str(key)
                yield from cls._iter_route_configs(child, child_path)
        elif isinstance(value, list):
            for idx, child in enumerate(value):
                child_path = f"{path}[{idx}]" if path else f"[{idx}]"
                yield from cls._iter_route_configs(child, child_path)

    @staticmethod
    def _model_size_b(model: str) -> float:
        match = _MODEL_SIZE_RE.search(str(model or ""))
        if not match:
            return 0.0
        try:
            return float(match.group(1))
        except Exception:
            return 0.0

    @classmethod
    def _weight_class(cls, model: str) -> str:
        size_b = cls._model_size_b(model)
        if size_b <= 0:
            return "unknown"
        if size_b <= 4:
            return "small"
        if size_b <= 9:
            return "normal"
        if size_b <= 14:
            return "heavy"
        if size_b >= 24:
            return "premium"
        return "large"

    @staticmethod
    def _weight_rank(weight_class: str) -> int:
        return {
            "unknown": 0,
            "small": 1,
            "normal": 2,
            "large": 3,
            "heavy": 4,
            "premium": 5,
        }.get(str(weight_class or ""), 0)

    def _configured_model_names(self) -> list[str]:
        out: list[str] = []
        servers = self._routing.get("llama_cpp_servers")
        if isinstance(servers, dict):
            for cfg in servers.values():
                if isinstance(cfg, dict):
                    for model_name in self._clean_model_list(cfg.get("models")):
                        self._append_unique(out, model_name)
        for model_name in self._clean_model_list(self._routing.get("premium_models")):
            self._append_unique(out, model_name)
        for _, cfg in self._iter_route_configs(self._routing):
            model_name = str(cfg.get("model") or "").strip()
            self._append_unique(out, model_name)
            for key in self._FALLBACK_KEYS:
                for fallback in self._clean_model_list(cfg.get(key)):
                    self._append_unique(out, fallback)
        return out

    def _ollama_tags(self, timeout: int = 5) -> tuple[bool, list[str], str]:
        if not isinstance(self._ollama, OllamaClient):
            try:
                models = self._ollama.list_local_models()
                return True, list(models) if isinstance(models, list) else [], ""
            except Exception as exc:
                return False, [], str(exc).strip()[:240]

        url = f"{self._ollama.base_url}/api/tags"
        req = urllib.request.Request(url=url, method="GET")
        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                data = json.loads(resp.read().decode("utf-8"))
        except urllib.error.URLError as exc:
            return False, [], str(exc).strip()[:240]
        except Exception as exc:
            return False, [], str(exc).strip()[:240]

        names: list[str] = []
        models = data.get("models") if isinstance(data, dict) else []
        if isinstance(models, list):
            for item in models:
                if not isinstance(item, dict):
                    continue
                name = str(item.get("name") or item.get("model") or "").strip()
                if name and name not in names:
                    names.append(name)
        return True, names, ""

    def _read_ollama_ps_json(self, timeout: int = 5) -> dict[str, Any]:
        if not isinstance(self._ollama, OllamaClient) and hasattr(self._ollama, "ps_json"):
            try:
                payload = self._ollama.ps_json()
                return dict(payload) if isinstance(payload, dict) else {}
            except Exception:
                return {}
        base_url = str(getattr(self._ollama, "base_url", "http://127.0.0.1:11434")).rstrip("/")
        url = f"{base_url}/api/ps"
        req = urllib.request.Request(url=url, method="GET")
        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                data = resp.read().decode("utf-8")
        except urllib.error.URLError:
            return {}
        except Exception:
            return {}
        try:
            payload = json.loads(data)
        except Exception:
            return {}
        return dict(payload) if isinstance(payload, dict) else {}

    def list_backends(self) -> list[dict[str, Any]]:
        """Return configured local inference backends and lightweight reachability state."""
        backends: list[dict[str, Any]] = []
        ollama_reachable, ollama_models, ollama_error = self._ollama_tags()
        ollama_backend: dict[str, Any] = {
            "name": "ollama",
            "kind": "ollama",
            "base_url": str(getattr(self._ollama, "base_url", "http://127.0.0.1:11434")),
            "reachable": ollama_reachable,
            "models": ollama_models,
        }
        if ollama_error:
            ollama_backend["error"] = ollama_error
        backends.append(ollama_backend)

        servers = self._routing.get("llama_cpp_servers")
        server_cfgs = servers if isinstance(servers, dict) else {}
        for server_key, client in self._llama_clients.items():
            cfg = server_cfgs.get(server_key, {}) if isinstance(server_cfgs.get(server_key, {}), dict) else {}
            configured_models = self._clean_model_list(cfg.get("models"))
            if not configured_models:
                configured_models = [model for model, mapped in self._model_map.items() if mapped == server_key]
            remaining = self._server_backoff_remaining_sec(server_key)
            served_models: list[str] = []
            reachable = False
            error = ""
            if remaining <= 0:
                try:
                    served_models = client.list_local_models_strict()
                    reachable = True
                    self._clear_server_backoff(server_key)
                except Exception as exc:
                    error = str(exc).strip()[:240]
                    self._mark_server_backoff(server_key)
                    remaining = self._server_backoff_remaining_sec(server_key)

            item: dict[str, Any] = {
                "name": server_key,
                "kind": "llama.cpp",
                "base_url": str(getattr(client, "base_url", "")),
                "reachable": reachable,
                "models": served_models,
                "configured_models": configured_models,
                "fallback_to_ollama": self._fallback_flags.get(server_key, False),
                "backoff_until_sec": remaining,
            }
            if error:
                item["error"] = error
            backends.append(item)
        return backends

    def fallback_chain(self, model: str) -> list[str]:
        """Return configured fallback candidates for a primary model, preserving order."""
        target = str(model or "").strip()
        chain: list[str] = []
        if not target:
            return chain
        for _, cfg in self._iter_route_configs(self._routing):
            primary = str(cfg.get("model") or "").strip()
            if primary != target:
                continue
            self._append_unique(chain, primary)
            for key in self._FALLBACK_KEYS:
                for fallback in self._clean_model_list(cfg.get(key)):
                    self._append_unique(chain, fallback)
        if not chain:
            chain.append(target)
        return chain

    def memory_state(self) -> dict[str, Any]:
        """Return currently loaded Ollama model state without triggering a load."""
        payload = self._read_ollama_ps_json()
        rows = payload.get("models") if isinstance(payload, dict) else []
        if not isinstance(rows, list):
            rows = []

        loaded_models: list[str] = []
        loaded_model = ""
        loaded_adapter = ""
        total_vram_used_gb = 0.0
        total_vram_capacity_gb = 0.0
        kv_pressure = 0.0

        for row in rows:
            if not isinstance(row, dict):
                continue
            name = str(row.get("name") or row.get("model") or "").strip()
            if name:
                self._append_unique(loaded_models, name)
                if not loaded_model:
                    loaded_model = name

            adapter = str(row.get("adapter") or row.get("lora") or "").strip()
            if adapter and not loaded_adapter:
                loaded_adapter = adapter

            total_vram_used_gb += max(
                0.0,
                _to_gb(row.get("size_vram") or row.get("vram_size") or row.get("gpu_memory")),
            )
            total_vram_capacity_gb = max(
                total_vram_capacity_gb,
                _to_gb(row.get("gpu_total") or row.get("vram_total") or row.get("gpu_capacity")),
            )
            kv = row.get("kv_cache_usage")
            if kv is None:
                kv = row.get("kv_usage")
            try:
                kv_val = float(kv)
            except Exception:
                kv_val = 0.0
            if kv_val > 1.0:
                kv_val = kv_val / 100.0
            kv_pressure = max(kv_pressure, max(0.0, min(1.0, kv_val)))

        free_vram_gb = 0.0
        if total_vram_capacity_gb > 0.0:
            free_vram_gb = max(0.0, total_vram_capacity_gb - total_vram_used_gb)

        return {
            "backend": "ollama",
            "loaded_model": loaded_model,
            "loaded_models": loaded_models,
            "loaded_adapter": loaded_adapter,
            "kv_pressure": kv_pressure,
            "free_vram_gb": float(round(free_vram_gb, 3)),
            "vram_used_gb": float(round(total_vram_used_gb, 3)),
            "vram_capacity_gb": float(round(total_vram_capacity_gb, 3)),
            "raw_model_count": len(loaded_models),
        }

    def is_loaded(self, model: str) -> bool:
        name = str(model or "").strip()
        return bool(name and name in self.memory_state().get("loaded_models", []))

    def context_window(self, model: str) -> int:
        name = str(model or "").strip()
        contexts: list[int] = []
        if not name:
            return 8192
        for _, cfg in self._iter_route_configs(self._routing):
            refs = [str(cfg.get("model") or "").strip()]
            for key in self._FALLBACK_KEYS:
                refs.extend(self._clean_model_list(cfg.get(key)))
            if name not in refs:
                continue
            try:
                ctx = int(cfg.get("num_ctx") or 0)
            except Exception:
                ctx = 0
            if ctx > 0:
                contexts.append(ctx)
        return max(contexts) if contexts else 8192

    def capabilities(self, model: str) -> dict[str, Any]:
        name = str(model or "").strip()
        premium_models = set(self._clean_model_list(self._routing.get("premium_models")))
        size_b = self._model_size_b(name)
        weight_class = self._weight_class(name)
        backends: list[str] = []
        if name in self._model_map:
            backends.append("llama.cpp")
        backends.append("ollama")
        low = name.lower()
        tasks = ["embedding"] if "embed" in low else ["chat"]
        return {
            "model": name,
            "configured": name in self._configured_model_names(),
            "premium": name in premium_models or weight_class == "premium",
            "size_b": size_b,
            "weight_class": weight_class,
            "context_window": self.context_window(name),
            "reasoning": low.startswith("deepseek-r1") or low.startswith("qwen3"),
            "tasks": tasks,
            "backends": backends,
        }

    def estimate_fit(
        self,
        model: str,
        num_ctx: int,
        concurrency: int = 1,
        profile: dict[str, Any] | str | None = None,
    ) -> dict[str, Any]:
        """Conservative policy estimate, not a hardware memory calculator."""
        if profile is None:
            profile = active_router_policy_from_env(self.repo_root)
        name = str(model or "").strip()
        caps = self.capabilities(name)
        warnings: list[str] = []
        fits = True
        confidence = "medium"

        max_context = 32768
        warning_context = 16384
        max_concurrency = 1
        allow_premium = False
        profile_name = "default_local_workstation"
        if isinstance(profile, dict):
            profile_name = str(profile.get("name") or profile_name)
            max_context = int(profile.get("max_context", max_context) or max_context)
            warning_context = int(profile.get("warning_context", warning_context) or warning_context)
            max_concurrency = int(profile.get("max_concurrency", max_concurrency) or max_concurrency)
            allow_premium = bool(profile.get("allow_premium", allow_premium))
        elif isinstance(profile, str) and profile.strip():
            profile_name = profile.strip()

        try:
            ctx = int(num_ctx)
        except Exception:
            ctx = 8192
        try:
            active = max(1, int(concurrency))
        except Exception:
            active = 1

        weight_class = str(caps.get("weight_class") or "unknown")
        if weight_class == "unknown":
            confidence = "low"
            warnings.append("Model size is unknown; fit estimate uses only context and concurrency policy.")
        elif weight_class in {"small", "normal"}:
            confidence = "medium"
        elif weight_class == "heavy":
            warnings.append("Heavy model class; prefer low concurrency and explicit operator intent.")
        elif weight_class == "premium":
            if allow_premium:
                warnings.append("Premium-size model allowed by profile; expect manual capacity planning.")
                confidence = "low"
            else:
                fits = False
                confidence = "high"
                warnings.append("Premium-size model is outside the default local workstation policy.")
        else:
            warnings.append("Large model class; verify available memory before loading.")

        if ctx > warning_context:
            warnings.append(f"Requested context {ctx} exceeds the profile warning threshold {warning_context}.")
        if ctx > max_context:
            fits = False
            warnings.append(f"Requested context {ctx} exceeds the profile cap {max_context}.")
        if active > max_concurrency:
            warnings.append(f"Requested concurrency {active} exceeds the profile default {max_concurrency}.")
            if active > 2 and weight_class in {"normal", "large", "heavy", "premium"}:
                fits = False

        if fits and not warnings:
            reason = f"{weight_class} model is within the conservative {profile_name} policy."
        elif fits:
            reason = f"{weight_class} model may fit under {profile_name}, with policy warnings."
        else:
            reason = f"{weight_class} model is outside the conservative {profile_name} policy."

        return {
            "model": name,
            "fits": fits,
            "confidence": confidence,
            "profile": profile_name,
            "size_b": caps.get("size_b", 0.0),
            "weight_class": weight_class,
            "num_ctx": ctx,
            "concurrency": active,
            "reason": reason,
            "warnings": warnings,
        }

    def health_report(self) -> dict[str, Any]:
        warnings: list[str] = []
        backends = self.list_backends()
        for backend in backends:
            if not backend.get("reachable"):
                warnings.append(f"{backend.get('name')} backend is not reachable.")
        loaded = self.memory_state()
        ok = any(bool(backend.get("reachable")) for backend in backends)
        model_health: dict[str, Any] = {}
        get_status = getattr(self._ollama, "get_status", None)
        if callable(get_status):
            try:
                status = get_status()
                if isinstance(status, dict):
                    model_health = status
            except Exception:
                model_health = {}
        return {
            "ok": ok,
            "backends": backends,
            "loaded_models": loaded.get("loaded_models", []),
            "memory_state": loaded,
            "ollama_model_health": model_health,
            "warnings": warnings,
        }

    def validate_config(
        self,
        *,
        strict: bool = False,
        check_remote: bool = True,
        profile: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        errors: list[str] = []
        warnings: list[str] = []
        referenced = self._configured_model_names()
        profile_policy: dict[str, Any] | None = None
        if isinstance(profile, dict):
            if "scheduler" in profile or "model_policy" in profile:
                profile_policy = hardware_profile_to_router_policy(profile)
            else:
                profile_policy = dict(profile)
        else:
            profile_policy = active_router_policy_from_env(self.repo_root)
        profile_name = str((profile_policy or {}).get("name") or "").strip()
        max_context = int((profile_policy or {}).get("max_context") or 32768)
        warning_context = int((profile_policy or {}).get("warning_context") or 16384)
        max_concurrency = int((profile_policy or {}).get("max_concurrency") or 2)
        allow_premium = bool((profile_policy or {}).get("allow_premium", False))
        lane_caps = (profile_policy or {}).get("lane_caps")
        lane_caps = lane_caps if isinstance(lane_caps, dict) else {}

        servers = self._routing.get("llama_cpp_servers")
        if servers is not None and not isinstance(servers, dict):
            errors.append("llama_cpp_servers must be an object when present.")
        if isinstance(servers, dict):
            seen_server_models: set[str] = set()
            for server_key, cfg in servers.items():
                if not isinstance(cfg, dict):
                    errors.append(f"llama_cpp_servers.{server_key} must be an object.")
                    continue
                base_url = str(cfg.get("base_url") or "").strip()
                if not base_url:
                    errors.append(f"llama_cpp_servers.{server_key}.base_url is empty.")
                models = cfg.get("models")
                if not isinstance(models, list):
                    errors.append(f"llama_cpp_servers.{server_key}.models must be a list.")
                    continue
                local_seen: set[str] = set()
                for raw in models:
                    name = str(raw or "").strip()
                    if not name:
                        errors.append(f"llama_cpp_servers.{server_key}.models contains an empty model name.")
                        continue
                    if name in local_seen or name in seen_server_models:
                        warnings.append(f"Duplicate llama.cpp model mapping: {name}.")
                    local_seen.add(name)
                    seen_server_models.add(name)

        referenced_set = set(referenced)
        premium_models = set(self._clean_model_list(self._routing.get("premium_models")))
        for path, cfg in self._iter_route_configs(self._routing):
            primary = str(cfg.get("model") or "").strip()
            if not primary and "model" in cfg:
                errors.append(f"{path}.model is empty.")
            primary_class = self._weight_class(primary)
            for key in self._FALLBACK_KEYS:
                for fallback in self._clean_model_list(cfg.get(key)):
                    if fallback not in referenced_set:
                        warnings.append(f"{path}.{key} references {fallback}, but no route or model list defines it.")
                    fallback_class = self._weight_class(fallback)
                    if self._weight_rank(fallback_class) > self._weight_rank(primary_class):
                        warnings.append(f"{path}.{key} fallback {fallback} appears heavier than primary {primary}.")
            if primary in premium_models and "tier_premium" not in path and not path.endswith("tier_premium"):
                warnings.append(f"{path}.model uses premium model {primary} outside an explicit premium tier.")
            try:
                ctx = int(cfg.get("num_ctx") or 0)
            except Exception:
                ctx = 0
            if ctx > max_context:
                if profile_name:
                    warnings.append(f"{path}.num_ctx={ctx} exceeds hardware profile {profile_name} cap {max_context}.")
                else:
                    errors.append(f"{path}.num_ctx={ctx} exceeds the default hard cap 32768.")
            elif ctx > warning_context:
                if profile_name:
                    warnings.append(
                        f"{path}.num_ctx={ctx} exceeds hardware profile {profile_name} warning threshold {warning_context}."
                    )
                else:
                    warnings.append(f"{path}.num_ctx={ctx} exceeds the conservative local warning threshold 16384.")
            try:
                parallel = int(cfg.get("parallel_agents") or 0)
            except Exception:
                parallel = 0
            if parallel > max_concurrency:
                if profile_name:
                    warnings.append(
                        f"{path}.parallel_agents={parallel} exceeds hardware profile {profile_name} concurrency {max_concurrency}."
                    )
                else:
                    warnings.append(f"{path}.parallel_agents={parallel} exceeds the conservative local default 2.")
            lane_key = str(path).split(".", 1)[0]
            cap = lane_caps.get(lane_key)
            cap = cap if isinstance(cap, dict) else {}
            try:
                lane_max_ctx = int(cap.get("max_context_tokens") or 0)
            except Exception:
                lane_max_ctx = 0
            if lane_max_ctx and ctx > lane_max_ctx:
                warnings.append(f"{path}.num_ctx={ctx} exceeds {profile_name or 'profile'} lane cap {lane_max_ctx}.")
            try:
                lane_max_parallel = int(cap.get("max_parallel_agents") or 0)
            except Exception:
                lane_max_parallel = 0
            if lane_max_parallel and parallel > lane_max_parallel:
                warnings.append(
                    f"{path}.parallel_agents={parallel} exceeds {profile_name or 'profile'} lane cap {lane_max_parallel}."
                )
            if cap.get("allow_premium") is False and (primary in premium_models or self._weight_class(primary) == "premium"):
                warnings.append(f"{path}.model uses premium model {primary}, but {profile_name or 'profile'} lane policy disallows premium.")
            if profile_name and not allow_premium and (primary in premium_models or self._weight_class(primary) == "premium"):
                warnings.append(f"{path}.model uses premium model {primary}, but hardware profile {profile_name} disallows premium.")

        if check_remote:
            backends = self.list_backends()
            installed: set[str] = set()
            saw_reachable_backend = False
            for backend in backends:
                if backend.get("reachable"):
                    saw_reachable_backend = True
                if backend.get("kind") == "llama.cpp" and backend.get("backoff_until_sec", 0):
                    warnings.append(f"{backend.get('name')} llama.cpp server is in backoff.")
                if not backend.get("reachable"):
                    warnings.append(f"{backend.get('name')} backend is not reachable.")
                for model_name in backend.get("models") or []:
                    installed.add(str(model_name))
            if saw_reachable_backend:
                for model_name in referenced:
                    if model_name not in installed:
                        msg = f"Configured model {model_name} is not present on any reachable backend."
                        if strict:
                            errors.append(msg)
                        else:
                            warnings.append(msg)

        return {
            "ok": not errors and (not strict or not warnings),
            "errors": errors,
            "warnings": warnings,
            "model_count": len(referenced),
            "profile": profile_name,
        }

    def explain_route(
        self,
        model: str | None = None,
        task_class: str | None = None,
        constraints: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        constraints = constraints if isinstance(constraints, dict) else {}
        lane_cfg = self._routing.get(str(task_class or ""), {})
        lane_cfg = lane_cfg if isinstance(lane_cfg, dict) else {}
        requested = str(model or lane_cfg.get("model") or "").strip()
        fallback_models = self._clean_model_list(constraints.get("fallback_models"))
        if not fallback_models:
            for key in self._FALLBACK_KEYS:
                fallback_models.extend(self._clean_model_list(lane_cfg.get(key)))
        chain = self._candidate_models(requested, fallback_models) if fallback_models else self.fallback_chain(requested)

        backends = self.list_backends()
        installed: set[str] = set()
        llama_served: set[str] = set()
        for backend in backends:
            for model_name in backend.get("models") or []:
                installed.add(str(model_name))
                if backend.get("kind") == "llama.cpp":
                    llama_served.add(str(model_name))

        selected = ""
        for candidate in chain:
            if candidate in installed:
                selected = candidate
                break
        if not selected and chain:
            selected = chain[0]

        server_key = self._model_map.get(selected, "")
        server_in_backoff = bool(server_key and self._server_in_backoff(server_key))
        backend = "llama.cpp" if selected in llama_served and not server_in_backoff else "ollama"
        try:
            num_ctx = int(constraints.get("num_ctx") or lane_cfg.get("num_ctx") or self.context_window(selected))
        except Exception:
            num_ctx = self.context_window(selected)
        try:
            concurrency = int(constraints.get("concurrency") or lane_cfg.get("parallel_agents") or 1)
        except Exception:
            concurrency = 1
        fit = self.estimate_fit(selected, num_ctx, concurrency=concurrency, profile=constraints.get("profile"))
        warnings = list(fit.get("warnings") or [])
        if requested and requested not in installed:
            warnings.append(f"Requested model {requested} is not present on any reachable backend.")
        if server_in_backoff:
            warnings.append(f"Configured llama.cpp server {server_key} is currently in backoff.")
        return {
            "requested_model": requested,
            "selected_model": selected,
            "task_class": str(task_class or ""),
            "backend": backend,
            "fallback_chain": chain,
            "installed": selected in installed,
            "loaded": self.is_loaded(selected),
            "server_in_backoff": server_in_backoff,
            "estimated_fit": fit,
            "warnings": warnings,
        }

    def chat(
        self,
        model: str,
        system_prompt: str,
        user_prompt: str,
        *,
        prior_messages: list[dict[str, str]] | None = None,
        user_images: list[str] | None = None,
        temperature: float = 0.3,
        num_ctx: int = 8192,
        think: bool | None = None,
        num_predict: int | None = -1,
        timeout: int = 300,
        retry_attempts: int = 1,
        retry_backoff_sec: float = 1.25,
        fallback_models: list[str] | None = None,
        keep_alive: str = "10m",
        task_class: str | None = None,
        artifact_importance: str | None = None,
        tier: str | None = None,
    ) -> str:
        _task_class = str(task_class or "").strip() or "-"
        _artifact_importance = str(artifact_importance or "").strip() or "-"
        _tier = str(tier or "").strip() or "-"
        kwargs: dict[str, Any] = dict(
            prior_messages=prior_messages,
            user_images=user_images,
            temperature=temperature,
            num_ctx=num_ctx,
            think=think,
            num_predict=num_predict,
            timeout=timeout,
            retry_attempts=retry_attempts,
            retry_backoff_sec=retry_backoff_sec,
        )
        cache_ttl = self._cache_ttl_for_call(
            task_class=str(task_class or ""),
            temperature=float(temperature or 0.0),
            think=think,
        )
        cache_key = ""
        if cache_ttl > 0:
            cache_key = self._response_cache_key(
                model=model,
                system_prompt=system_prompt,
                user_prompt=user_prompt,
                prior_messages=prior_messages,
                user_images=user_images,
                temperature=temperature,
                num_ctx=num_ctx,
                think=think,
                num_predict=num_predict,
                task_class=str(task_class or ""),
            )
            cached = self._cache_get(cache_key)
            if cached is not None:
                LOGGER.debug("inference_call cache_hit model=%s task_class=%s", model, _task_class)
                return cached
        errors: list[str] = []
        _call_start = time.perf_counter()
        for _cand_idx, candidate in enumerate(self._candidate_models(model, fallback_models)):
            routed_to_llama = self._server_declares_model(candidate)
            client = self._llama_clients[self._model_map[candidate]] if routed_to_llama else self._ollama
            _route = "llama.cpp" if routed_to_llama else "ollama"
            _attempt_start = time.perf_counter()
            # keep_alive is Ollama-specific — only include it when routing to Ollama
            call_kwargs = dict(kwargs, fallback_models=[])
            if not routed_to_llama:
                call_kwargs["keep_alive"] = keep_alive
            try:
                result = client.chat(
                    candidate,
                    system_prompt,
                    user_prompt,
                    **call_kwargs,
                )
                LOGGER.info(
                    "inference_call model=%s route=%s tier=%s task_class=%s artifact_importance=%s elapsed=%.3fs total=%.3fs attempts=%d fallback=%s status=ok",
                    candidate, _route,
                    _tier, _task_class, _artifact_importance,
                    round(time.perf_counter() - _attempt_start, 3),
                    round(time.perf_counter() - _call_start, 3),
                    _cand_idx + 1, _cand_idx > 0,
                )
                if cache_key and cache_ttl > 0 and str(result or "").strip():
                    self._cache_put(cache_key, str(result), cache_ttl)
                return result
            except RuntimeError as exc:
                _attempt_elapsed = round(time.perf_counter() - _attempt_start, 3)
                errors.append(f"{candidate} via {_route}: {exc}")
                LOGGER.warning(
                    "inference_call model=%s route=%s tier=%s task_class=%s artifact_importance=%s elapsed=%.3fs attempt=%d status=fail error=%s",
                    candidate, _route, _tier, _task_class, _artifact_importance,
                    _attempt_elapsed, _cand_idx + 1, str(exc)[:120],
                )
                if routed_to_llama:
                    server_key = self._model_map.get(candidate, "")
                    self._mark_server_backoff(server_key)
                    if self._should_fallback(candidate):
                        _fb_start = time.perf_counter()
                        try:
                            LOGGER.warning("llama.cpp server failed for %s, falling back to Ollama", candidate)
                            result = self._ollama.chat(
                                candidate,
                                system_prompt,
                                user_prompt,
                                **dict(kwargs, fallback_models=[], keep_alive=keep_alive),
                            )
                            LOGGER.info(
                                "inference_call model=%s route=ollama_fallback tier=%s task_class=%s artifact_importance=%s elapsed=%.3fs total=%.3fs attempts=%d fallback=true status=ok",
                                candidate,
                                _tier, _task_class, _artifact_importance,
                                round(time.perf_counter() - _fb_start, 3),
                                round(time.perf_counter() - _call_start, 3),
                                _cand_idx + 1,
                            )
                            if cache_key and cache_ttl > 0 and str(result or "").strip():
                                self._cache_put(cache_key, str(result), cache_ttl)
                            return result
                        except RuntimeError as ollama_exc:
                            errors.append(f"{candidate} via ollama fallback: {ollama_exc}")
                            LOGGER.warning(
                                "inference_call model=%s route=ollama_fallback tier=%s task_class=%s artifact_importance=%s elapsed=%.3fs attempt=%d status=fail",
                                candidate, _tier, _task_class, _artifact_importance,
                                round(time.perf_counter() - _fb_start, 3), _cand_idx + 1,
                            )
                continue

        tail = " | ".join(errors[-8:]) if errors else "No model candidates were available."
        raise RuntimeError(f"InferenceRouter chat failed after routed retries/fallbacks: {tail}")

    def warmup_models(self, models: list[str]) -> None:
        """Fire lightweight prompts to warm model runtime caches."""
        for model in models:
            name = str(model or "").strip()
            if not name:
                continue
            try:
                self.chat(
                    name,
                    "Return exactly: warm",
                    "warm",
                    temperature=0.0,
                    num_ctx=256,
                    think=False,
                    timeout=20,
                    retry_attempts=1,
                    retry_backoff_sec=0.2,
                    fallback_models=[],
                    keep_alive="20m",
                    task_class="warmup",
                )
            except Exception:
                continue

    def wait_for_available(
        self,
        model: str,
        *,
        fallback_models: list[str] | None = None,
        max_wait_sec: int = 300,
        poll_interval_sec: int = 15,
    ) -> bool:
        """Reachability check for any of {model, *fallback_models}.

        Preflight must not trigger model loads. This checks llama.cpp declarations
        and then delegates to Ollama metadata probes when needed.
        """
        candidates: list[str] = []
        for item in [model, *(fallback_models or [])]:
            entry = str(item or "").strip()
            if entry and entry not in candidates:
                candidates.append(entry)
        if not candidates:
            return False
        self.last_wait_error = ""
        self.last_wait_candidates = list(candidates)
        self.last_wait_polls = 0
        self.last_wait_elapsed_sec = 0
        started = time.monotonic()
        deadline = started + float(max_wait_sec)
        polls = 0
        last_error = ""
        while time.monotonic() < deadline:
            polls += 1
            # Fast path for mapped llama.cpp servers.
            for cand in candidates:
                try:
                    if self._server_declares_model(cand):
                        self.last_wait_error = ""
                        self.last_wait_polls = polls
                        self.last_wait_elapsed_sec = int(max(0.0, time.monotonic() - started))
                        return True
                except Exception as exc:
                    last_error = f"llama.cpp probe {cand}: {str(exc).strip()[:240]}"

            remaining_sec = max(1, int(deadline - time.monotonic()))
            if remaining_sec <= 0:
                break
            try:
                inner_wait = min(remaining_sec, int(max(1.0, float(poll_interval_sec))) + 5)
                inner_poll = min(
                    max(1.0, float(poll_interval_sec)),
                    max(1.0, inner_wait / 2.0),
                )
                if self._ollama.wait_for_available(
                    candidates[0],
                    fallback_models=candidates[1:],
                    max_wait_sec=inner_wait,
                    poll_interval_sec=int(inner_poll),
                ):
                    self.last_wait_error = ""
                    self.last_wait_polls = polls + int(self._ollama.last_wait_polls or 0)
                    self.last_wait_elapsed_sec = int(max(0.0, time.monotonic() - started))
                    return True
                if str(self._ollama.last_wait_error or "").strip():
                    last_error = str(self._ollama.last_wait_error).strip()
            except Exception as exc:
                last_error = f"{type(exc).__name__}: {str(exc).strip()[:240]}"

            elapsed = int(max(0.0, time.monotonic() - started))
            LOGGER.debug(
                "wait_for_available: candidates=%s not ready, elapsed=%ds, error=%s",
                candidates,
                elapsed,
                last_error or "unknown",
            )
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                break
            time.sleep(min(float(poll_interval_sec), max(0.0, remaining)))
        elapsed = int(max(0.0, time.monotonic() - started))
        self.last_wait_error = last_error or "unknown"
        self.last_wait_polls = polls
        self.last_wait_elapsed_sec = elapsed
        LOGGER.warning(
            "wait_for_available timeout: candidates=%s elapsed=%ds polls=%d last_error=%s",
            candidates,
            elapsed,
            polls,
            last_error or "unknown",
        )
        return False

    def wait_for_any(
        self,
        models: list[str],
        *,
        max_wait_sec: int = 300,
        poll_interval_sec: int = 15,
    ) -> bool:
        candidates = self._candidate_models("", models)
        if not candidates:
            return False
        return self.wait_for_available(
            candidates[0],
            fallback_models=candidates[1:],
            max_wait_sec=max_wait_sec,
            poll_interval_sec=poll_interval_sec,
        )

    def release_models(self, models: list[str]) -> None:
        """Release Ollama-hosted models from VRAM after a pool run completes.

        Only releases models NOT in the llama.cpp model map — those are managed
        by the external server process, not Ollama's VRAM scheduler.
        """
        for model in models:
            if not model:
                continue
            if model not in self._model_map:
                self._ollama.release_model(model)

    def embed(self, model: str, text: str, *, timeout: int = 60) -> list[float]:
        return self._ollama.embed(model, text, timeout=timeout)

    def list_local_models(self) -> list[str]:
        models = self._ollama.list_local_models()
        for model_name in self._model_map:
            if model_name not in models:
                models.append(model_name)
        return models
