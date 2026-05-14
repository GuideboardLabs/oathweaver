"""Embedding-backed semantic routing gate for web vs no_web decisions."""

from __future__ import annotations

import hmac
import hashlib
import json
import logging
import math
import secrets
from pathlib import Path
from threading import Lock
from typing import Any

from shared_tools.model_routing import lane_model_config
from shared_tools.ollama_client import OllamaClient
from shared_tools.secret_files import ensure_secret_mode, write_secret_text

LOGGER = logging.getLogger(__name__)


def _vec_cosine(a: list[float], b: list[float]) -> float:
    if not a or not b or len(a) != len(b):
        return 0.0
    dot = sum(x * y for x, y in zip(a, b))
    na = math.sqrt(sum(x * x for x in a))
    nb = math.sqrt(sum(y * y for y in b))
    if na <= 0 or nb <= 0:
        return 0.0
    return dot / (na * nb)


def _normalize(text: str) -> str:
    return " ".join(str(text or "").strip().lower().split())


def _routes_signature(embed_model: str, routes: dict[str, list[str]]) -> str:
    normalized = {
        key: [_normalize(x) for x in value if _normalize(x)]
        for key, value in sorted(routes.items(), key=lambda x: x[0])
    }
    payload = {"embed_model": embed_model, "routes": normalized}
    return hashlib.sha256(json.dumps(payload, sort_keys=True, ensure_ascii=True).encode("utf-8")).hexdigest()


class SemanticGate:
    """Small semantic router using local embeddings and persisted route vectors."""

    def __init__(
        self,
        repo_root: Path,
        *,
        routes: dict[str, list[str]],
        threshold: float = 0.72,
    ) -> None:
        self.repo_root = repo_root
        self.threshold = max(0.1, min(float(threshold), 0.99))
        self.routes = {
            str(key): [text for text in (values or []) if _normalize(text)]
            for key, values in routes.items()
            if str(key).strip()
        }
        embed_cfg = lane_model_config(repo_root, "embeddings")
        self.embed_model = str(embed_cfg.get("model", "qwen3-embedding:4b")).strip() or "qwen3-embedding:4b"
        self._client = OllamaClient()
        self._cache_path = repo_root / "Runtime" / "routing" / "semantic_routes.json"
        self._legacy_cache_path = repo_root / "Runtime" / "routing" / "semantic_routes.pkl"
        self._hmac_key_path = repo_root / "Runtime" / "state" / "semantic_routes_hmac.key"
        self._cache_path.parent.mkdir(parents=True, exist_ok=True)
        self._index_lock = Lock()
        self._index: dict[str, list[tuple[str, list[float]]]] = {}
        self._signature = _routes_signature(self.embed_model, self.routes)
        self._load_or_build_index()

    def classify(self, text: str) -> dict[str, Any] | None:
        query = _normalize(text)
        if not query:
            return None
        with self._index_lock:
            if not self._index:
                return None
        query_vec = self._client.embed(self.embed_model, query, timeout=20)
        scores: dict[str, float] = {}
        with self._index_lock:
            for route, rows in self._index.items():
                best = 0.0
                for _, vec in rows:
                    score = _vec_cosine(query_vec, vec)
                    if score > best:
                        best = score
                scores[route] = round(float(best), 4)
        if not scores:
            return None
        route = max(scores.items(), key=lambda x: x[1])[0]
        confidence = float(scores.get(route, 0.0))
        if confidence < self.threshold:
            return {
                "route": route,
                "confidence": confidence,
                "below_threshold": True,
                "scores": scores,
            }
        return {
            "route": route,
            "confidence": confidence,
            "below_threshold": False,
            "scores": scores,
        }

    def _load_or_build_index(self) -> None:
        loaded = self._try_load_cache()
        if loaded:
            return
        built = self._build_index()
        with self._index_lock:
            self._index = built
        self._save_cache()

    def _build_index(self) -> dict[str, list[tuple[str, list[float]]]]:
        built: dict[str, list[tuple[str, list[float]]]] = {}
        for route, examples in self.routes.items():
            vectors: list[tuple[str, list[float]]] = []
            for phrase in examples:
                norm = _normalize(phrase)
                if not norm:
                    continue
                try:
                    vec = self._client.embed(self.embed_model, norm, timeout=20)
                except Exception:
                    LOGGER.debug("SemanticGate embed failed for route=%s phrase=%s", route, phrase)
                    continue
                vectors.append((norm, vec))
            if vectors:
                built[route] = vectors
        return built

    def _try_load_cache(self) -> bool:
        if not self._cache_path.exists():
            # Explicitly ignore the legacy pickle cache and rebuild safely.
            if self._legacy_cache_path.exists():
                LOGGER.info("SemanticGate rebuilding legacy pickle cache as signed JSON.")
            return False
        try:
            raw = self._cache_path.read_bytes()
            mac_hex, payload_json = raw.split(b"\n", 1)
            expected = hmac.new(self._hmac_key(), payload_json, hashlib.sha256).hexdigest().encode("ascii")
            if not hmac.compare_digest(mac_hex.strip(), expected):
                return False
            payload = json.loads(payload_json.decode("utf-8"))
            if not isinstance(payload, dict):
                return False
            if str(payload.get("signature", "")) != self._signature:
                return False
            idx = payload.get("index", {})
            if not isinstance(idx, dict):
                return False
            loaded: dict[str, list[tuple[str, list[float]]]] = {}
            for route, rows in idx.items():
                if not isinstance(rows, list):
                    continue
                valid_rows: list[tuple[str, list[float]]] = []
                for item in rows:
                    if not isinstance(item, (list, tuple)) or len(item) != 2:
                        continue
                    phrase, vec = item
                    if not isinstance(phrase, str) or not isinstance(vec, list):
                        continue
                    try:
                        valid_rows.append((phrase, [float(x) for x in vec]))
                    except Exception:
                        continue
                if valid_rows:
                    loaded[str(route)] = valid_rows
            if not loaded:
                return False
            with self._index_lock:
                self._index = loaded
            return True
        except Exception:
            return False

    def _save_cache(self) -> None:
        with self._index_lock:
            payload = {
                "signature": self._signature,
                "index": self._index,
            }
        payload_json = json.dumps(payload, sort_keys=True, ensure_ascii=True).encode("utf-8")
        mac_hex = hmac.new(self._hmac_key(), payload_json, hashlib.sha256).hexdigest()
        body = f"{mac_hex}\n".encode("ascii") + payload_json
        tmp = self._cache_path.with_suffix(".tmp")
        try:
            write_secret_text(tmp, body.decode("utf-8"))
            tmp.replace(self._cache_path)
            ensure_secret_mode(self._cache_path)
        except Exception:
            try:
                tmp.unlink(missing_ok=True)
            except Exception:
                pass

    def _hmac_key(self) -> bytes:
        try:
            if self._hmac_key_path.exists():
                key_hex = self._hmac_key_path.read_text(encoding="utf-8").strip()
                key = bytes.fromhex(key_hex)
                if key:
                    ensure_secret_mode(self._hmac_key_path)
                    return key
        except Exception:
            pass
        key = secrets.token_bytes(32)
        write_secret_text(self._hmac_key_path, key.hex())
        return key
