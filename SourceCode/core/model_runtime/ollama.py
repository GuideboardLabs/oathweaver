from __future__ import annotations

import json
import re
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

from shared_tools.inference_router import InferenceRouter
from shared_tools.ollama_client import OllamaClient

from .base import GenerateRequest, ModelRuntime


_SIZE_RE = re.compile(r"^\s*([0-9]+(?:\.[0-9]+)?)\s*([kmgt]?i?b)?\s*$", flags=re.IGNORECASE)


def _to_gb(raw: Any) -> float:
    if raw is None:
        return 0.0
    if isinstance(raw, (int, float)):
        val = float(raw)
        # Assume bytes for large integers.
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
    if unit in {"b"}:
        return number / (1024.0 ** 3)
    if unit in {"kb", "kib"}:
        return number / (1024.0 ** 2)
    if unit in {"mb", "mib"}:
        return number / 1024.0
    if unit in {"gb", "gib"}:
        return number
    if unit in {"tb", "tib"}:
        return number * 1024.0
    return number


class OllamaModelRuntime(ModelRuntime):
    """ModelRuntime implementation backed by Ollama/InferenceRouter."""

    def __init__(
        self,
        repo_root: Path,
        *,
        router: InferenceRouter | None = None,
        ollama_client: OllamaClient | None = None,
        default_context_limit: int = 8192,
    ) -> None:
        self.repo_root = Path(repo_root)
        self.router = router or InferenceRouter(self.repo_root)
        self.ollama = ollama_client or OllamaClient()
        self.default_context_limit = max(512, int(default_context_limit))

    def generate(self, request: GenerateRequest) -> str:
        return self.router.chat(
            request.model,
            request.system_prompt,
            request.user_prompt,
            prior_messages=request.prior_messages,
            user_images=request.user_images,
            temperature=float(request.temperature),
            num_ctx=int(request.num_ctx),
            think=request.think,
            num_predict=request.num_predict,
            timeout=int(request.timeout),
        )

    def embed(self, texts: list[str], *, model: str) -> list[list[float]]:
        out: list[list[float]] = []
        for text in texts:
            out.append(self.ollama.embed(model, str(text or "")))
        return out

    def tokenize(self, text: str, *, model: str = "") -> list[int]:
        # Lightweight fallback tokenizer proxy for budgeting logic.
        tokens = [w for w in str(text or "").split() if w.strip()]
        return list(range(len(tokens)))

    def get_context_limit(self, *, model: str = "") -> int:
        _ = model
        return int(self.default_context_limit)

    def get_memory_state(self) -> dict[str, Any]:
        payload = self._read_ps_json()
        rows = payload.get("models", []) if isinstance(payload.get("models", []), list) else []

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
                loaded_models.append(name)
                if not loaded_model:
                    loaded_model = name

            adapter = str(row.get("adapter") or row.get("lora") or "").strip()
            if adapter and not loaded_adapter:
                loaded_adapter = adapter

            vram_used = _to_gb(row.get("size_vram") or row.get("vram_size") or row.get("gpu_memory"))
            total_vram_used_gb += max(0.0, vram_used)

            vram_total = _to_gb(row.get("gpu_total") or row.get("vram_total") or row.get("gpu_capacity"))
            total_vram_capacity_gb = max(total_vram_capacity_gb, vram_total)

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
            "free_ram_gb": 0.0,
            "context_limit": self.get_context_limit(model=loaded_model),
            "raw_model_count": len(loaded_models),
        }

    def _read_ps_json(self) -> dict[str, Any]:
        url = f"{self.ollama.base_url}/api/ps"
        req = urllib.request.Request(url=url, method="GET")
        try:
            with urllib.request.urlopen(req, timeout=5) as resp:
                data = resp.read().decode("utf-8")
        except urllib.error.URLError:
            return {}
        try:
            payload = json.loads(data)
        except Exception:
            return {}
        return dict(payload) if isinstance(payload, dict) else {}
