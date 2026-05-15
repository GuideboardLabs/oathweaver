from __future__ import annotations

import hashlib
import json
import math
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from shared_tools.model_routing import lane_model_config


def _normalize(text: str) -> str:
    return " ".join(str(text or "").strip().lower().split())


def _vec_cosine(a: list[float], b: list[float]) -> float:
    if not a or not b or len(a) != len(b):
        return 0.0
    dot = sum(x * y for x, y in zip(a, b))
    na = math.sqrt(sum(x * x for x in a))
    nb = math.sqrt(sum(y * y for y in b))
    if na <= 0 or nb <= 0:
        return 0.0
    return dot / (na * nb)


_EXEMPLARS: dict[str, list[str]] = {
    "model": [
        "what model are you running",
        "what model are you",
        "which model is this",
        "what's the model name",
        "what llm is this",
        "are you running locally",
    ],
    "routing": [
        "what's your fallback chain",
        "show me your routing",
        "why did you pick that model",
        "what model routing are you using",
        "what model does research use",
    ],
    "backend": [
        "is llama.cpp running",
        "what backends are available",
        "is ollama reachable",
        "what inference backend are you using",
    ],
    "loaded": [
        "what's loaded in vram",
        "what models are loaded",
        "how much vram is used",
        "what's your kv pressure",
    ],
    "hardware": [
        "what gpu are you on",
        "how much vram do you have",
        "what's your hardware profile",
        "are you on cuda",
        "are you on rocm",
        "what hardware are you running on",
        "why won't you load a bigger model",
        "are you allowed to use premium models",
        "what's your hardware policy",
    ],
    "capability": [
        "what are your capabilities",
        "what can you do",
        "what's your context window",
        "what tools do you have",
        "what's your context limit",
    ],
    "general": [
        "show me your config",
        "what's your current state",
        "tell me about yourself",
        "describe your setup",
        "how are you configured",
    ],
}


@dataclass(frozen=True)
class SelfQueryDecision:
    is_self_query: bool
    match_kind: str
    confidence: float
    matched_exemplar: str


class SelfQueryGate:
    def __init__(self, embed_client: Any, *, threshold: float = 0.75, repo_root: Path) -> None:
        self._embed_client = embed_client
        self.threshold = max(0.1, min(float(threshold), 0.99))
        self.repo_root = Path(repo_root)
        embed_cfg = lane_model_config(self.repo_root, "embeddings")
        self.embed_model = str(embed_cfg.get("model", "qwen3-embedding:4b")).strip() or "qwen3-embedding:4b"
        self._cache_path = self.repo_root / "Runtime" / "routing" / "self_query_gate.json"
        self._cache_path.parent.mkdir(parents=True, exist_ok=True)
        self._index: dict[str, list[tuple[str, list[float]]]] = {}
        self._signature = self._build_signature()
        self._load_or_build_index()

    def classify(self, text: str) -> SelfQueryDecision:
        query = _normalize(text)
        if not query:
            return SelfQueryDecision(False, "", 0.0, "")
        if not self._index:
            return SelfQueryDecision(False, "", 0.0, "")
        if self._is_near_miss_non_self_query(query):
            return SelfQueryDecision(False, "", 0.0, "")

        query_vec = self._embed_client.embed(self.embed_model, query, timeout=20)
        winner_kind = ""
        winner_score = 0.0
        winner_phrase = ""
        for kind, rows in self._index.items():
            best_score = 0.0
            best_phrase = ""
            for phrase, vec in rows:
                score = _vec_cosine(query_vec, vec)
                if score > best_score:
                    best_score = score
                    best_phrase = phrase
            if best_score > winner_score:
                winner_score = best_score
                winner_kind = kind
                winner_phrase = best_phrase

        is_hit = winner_score >= self.threshold and bool(winner_kind)
        return SelfQueryDecision(
            is_self_query=is_hit,
            match_kind=winner_kind if is_hit else "",
            confidence=float(round(winner_score, 4)),
            matched_exemplar=winner_phrase if is_hit else "",
        )

    @staticmethod
    def _is_near_miss_non_self_query(query: str) -> bool:
        text = _normalize(query)
        if re.search(r"\bmodel\s+car\b", text):
            return True
        if text.startswith("tell me about ollama") and "in general" in text:
            return True
        return False

    def _build_signature(self) -> str:
        payload = {
            "embed_model": self.embed_model,
            "exemplars": {k: [_normalize(x) for x in v] for k, v in sorted(_EXEMPLARS.items())},
        }
        raw = json.dumps(payload, sort_keys=True, ensure_ascii=True)
        return hashlib.sha256(raw.encode("utf-8")).hexdigest()

    def _load_or_build_index(self) -> None:
        if self._try_load_cache():
            return
        self._index = self._build_index()
        self._save_cache()

    def _build_index(self) -> dict[str, list[tuple[str, list[float]]]]:
        out: dict[str, list[tuple[str, list[float]]]] = {}
        for kind, phrases in _EXEMPLARS.items():
            rows: list[tuple[str, list[float]]] = []
            for phrase in phrases:
                norm = _normalize(phrase)
                if not norm:
                    continue
                try:
                    vec = self._embed_client.embed(self.embed_model, norm, timeout=20)
                except Exception:
                    continue
                rows.append((norm, [float(x) for x in vec]))
            if rows:
                out[kind] = rows
        return out

    def _try_load_cache(self) -> bool:
        if not self._cache_path.exists():
            return False
        try:
            payload = json.loads(self._cache_path.read_text(encoding="utf-8"))
        except Exception:
            return False
        if not isinstance(payload, dict):
            return False
        if str(payload.get("signature", "")).strip() != self._signature:
            return False
        idx = payload.get("index", {})
        if not isinstance(idx, dict):
            return False
        loaded: dict[str, list[tuple[str, list[float]]]] = {}
        for kind, rows in idx.items():
            if not isinstance(rows, list):
                continue
            parsed_rows: list[tuple[str, list[float]]] = []
            for row in rows:
                if not isinstance(row, (list, tuple)) or len(row) != 2:
                    continue
                phrase = str(row[0] or "").strip()
                vec = row[1]
                if not phrase or not isinstance(vec, list):
                    continue
                try:
                    parsed_rows.append((phrase, [float(x) for x in vec]))
                except Exception:
                    continue
            if parsed_rows:
                loaded[str(kind)] = parsed_rows
        if not loaded:
            return False
        self._index = loaded
        return True

    def _save_cache(self) -> None:
        payload = {
            "signature": self._signature,
            "index": self._index,
        }
        tmp = self._cache_path.with_suffix(".tmp")
        try:
            tmp.write_text(json.dumps(payload, ensure_ascii=True, sort_keys=True), encoding="utf-8")
            tmp.replace(self._cache_path)
        except Exception:
            try:
                tmp.unlink(missing_ok=True)
            except Exception:
                pass
