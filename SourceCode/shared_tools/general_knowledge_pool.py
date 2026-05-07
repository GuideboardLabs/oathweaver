"""
general_knowledge_pool.py — Lightweight cross-chat general knowledge store.

Saves a rolling log of talk-mode conversation summaries so future chats can
inherit context from prior conversations. No LLM calls — pure string ops.

Design:
  - Max 100 entries, FIFO (oldest dropped when full)
  - Each entry: {ts, topic_hint, summary}
  - Query: keyword token-overlap search, returns top N summaries
  - Storage: Runtime/memory/general_knowledge_pool.json
"""
from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from pathlib import Path
from threading import Lock
from typing import Any

_MAX_ENTRIES = 100
_SUMMARY_MAX_CHARS = 200
_TOPIC_MAX_CHARS = 80
_STOP_WORDS = frozenset([
    "a", "an", "the", "is", "it", "in", "on", "at", "to", "of", "and",
    "or", "for", "with", "that", "this", "was", "are", "be", "i", "you",
    "me", "my", "do", "can", "tell", "what", "how", "why", "who", "when",
    "more", "about", "some", "any", "just", "like", "get", "have", "its",
])


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _tokens(text: str) -> set[str]:
    return {w for w in re.findall(r"\w+", text.lower()) if w not in _STOP_WORDS and len(w) > 2}


def _token_overlap(a: str, b: str) -> float:
    ta = _tokens(a)
    tb = _tokens(b)
    if not ta or not tb:
        return 0.0
    return len(ta & tb) / len(ta | tb)


def _atomic_write(path: Path, data: Any) -> None:
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(data, indent=2, ensure_ascii=True), encoding="utf-8")
    tmp.replace(path)


class GeneralKnowledgePool:
    def __init__(self, repo_root: Path) -> None:
        self.path = repo_root / "Runtime" / "memory" / "general_knowledge_pool.json"
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.lock = Lock()

    def _load(self) -> list[dict[str, Any]]:
        if not self.path.exists():
            return []
        try:
            data = json.loads(self.path.read_text(encoding="utf-8"))
            return data if isinstance(data, list) else []
        except Exception:
            return []

    def save(self, topic_hint: str, summary: str) -> None:
        """Append a new entry to the pool. Thread-safe."""
        topic_hint = str(topic_hint or "").strip()[:_TOPIC_MAX_CHARS]
        summary = str(summary or "").strip()[:_SUMMARY_MAX_CHARS]
        if not summary:
            return
        with self.lock:
            entries = self._load()
            entries.append({"ts": _now_iso(), "topic_hint": topic_hint, "summary": summary})
            if len(entries) > _MAX_ENTRIES:
                entries = entries[-_MAX_ENTRIES:]
            try:
                _atomic_write(self.path, entries)
            except Exception:
                pass

    def query(self, text: str, n: int = 3) -> list[str]:
        """Return top N summaries by keyword overlap with text. Thread-safe."""
        text = str(text or "").strip()
        if not text:
            return []
        with self.lock:
            entries = self._load()
        if not entries:
            return []
        scored = []
        for entry in entries:
            hint = str(entry.get("topic_hint", ""))
            summary = str(entry.get("summary", ""))
            score = max(_token_overlap(text, hint), _token_overlap(text, summary))
            if score > 0.05:
                scored.append((score, summary))
        scored.sort(key=lambda x: x[0], reverse=True)
        return [s for _, s in scored[:n]]

    def remove_matching_summary(self, text: str, *, min_overlap: float = 0.58) -> int:
        """Remove entries whose summaries closely match the provided text."""
        needle = str(text or "").strip()
        if not needle:
            return 0
        removed = 0
        with self.lock:
            entries = self._load()
            kept: list[dict[str, Any]] = []
            for entry in entries:
                summary = str(entry.get("summary", "")).strip()
                if not summary:
                    continue
                overlap = max(_token_overlap(needle, summary), _token_overlap(summary, needle))
                if overlap >= min_overlap or summary in needle or needle in summary:
                    removed += 1
                    continue
                kept.append(entry)
            if removed:
                try:
                    _atomic_write(self.path, kept[-_MAX_ENTRIES:])
                except Exception:
                    return 0
        return removed
