"""
topic_memory.py — Semantic Topic Memory for Oathweaver

Extracts factual claims from web research results, stores them in a
hierarchical topic store, and surfaces high-confidence canon facts for
prompt injection. Medium-confidence facts are queued as yes/no review
items in the Postbag (pending actions overlay).

Confidence thresholds:
  >= 0.80  → auto-canon (silently merged)
  0.60-0.79 → pending review (Postbag)
  < 0.60   → discarded
"""
from __future__ import annotations

import json
import math
import re
import uuid
from datetime import datetime, timezone
from pathlib import Path
from threading import Lock
from typing import Any


_CONF_AUTO_CANON = 0.80
_CONF_MIN_REVIEW = 0.60
_MAX_FACTS_INJECT = 10
_MAX_CLAIM_CHARS = 120
_SIMILARITY_THRESHOLD = 0.75   # token overlap ratio for dedup
_MAX_SOURCES_FOR_EXTRACT = 8   # how many source snippets to send to Ollama


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _atomic_write(path: Path, data: dict[str, Any]) -> None:
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(data, indent=2, ensure_ascii=True), encoding="utf-8")
    tmp.replace(path)


def _load_json(path: Path, default: dict[str, Any]) -> dict[str, Any]:
    if not path.exists():
        return default
    try:
        loaded = json.loads(path.read_text(encoding="utf-8"))
        return loaded if isinstance(loaded, dict) else default
    except Exception:
        return default


def _vec_cosine(a: list[float], b: list[float]) -> float:
    if not a or not b or len(a) != len(b):
        return 0.0
    dot = sum(x * y for x, y in zip(a, b))
    na = math.sqrt(sum(x * x for x in a))
    nb = math.sqrt(sum(x * x for x in b))
    if na == 0 or nb == 0:
        return 0.0
    return dot / (na * nb)


def _token_overlap(a: str, b: str) -> float:
    """Jaccard token overlap between two strings."""
    ta = set(re.findall(r"\w+", a.lower()))
    tb = set(re.findall(r"\w+", b.lower()))
    if not ta or not tb:
        return 0.0
    return len(ta & tb) / len(ta | tb)


class TopicMemory:
    def __init__(self, repo_root: Path) -> None:
        self.repo_root = repo_root
        self.root = repo_root / "Runtime" / "memory"
        self.topics_dir = self.root / "topics"
        self.index_path = self.root / "topic_index.json"
        self.reviews_path = self.root / "topic_reviews.json"
        self.lock = Lock()
        self.topics_dir.mkdir(parents=True, exist_ok=True)
        self._embed_cache: dict[str, list[float]] = {}

    # ── Public API ────────────────────────────────────────────────────────

    def extract_and_merge_from_research(
        self,
        result: dict[str, Any],
        *,
        ollama_client: Any = None,
        model_cfg: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """
        Called after web_engine.approve_and_run() succeeds.
        Returns {"topics_touched": [...], "canon_added": N, "reviews_created": N}.
        """
        query = str(result.get("query", "")).strip()
        sources = result.get("sources", []) or []
        project = str(result.get("project", "general")).strip()
        source_file = str(result.get("source_path", "")).strip()

        if not query or not sources:
            return {"topics_touched": [], "canon_added": 0, "reviews_created": 0}

        # Extract topic/fact pairs via Ollama or heuristic fallback
        extracted: list[dict[str, Any]] = []
        if ollama_client is not None:
            try:
                extracted = self._call_ollama_extract(
                    query, sources, ollama_client, model_cfg or {}
                ) or []
            except Exception:
                extracted = []

        if not extracted:
            extracted = self._heuristic_extract(query, sources)

        canon_added = 0
        reviews_created = 0
        topics_touched: set[str] = set()

        for item in extracted:
            claim = str(item.get("claim", "")).strip()
            if not claim:
                continue
            confidence = float(item.get("confidence", 0.0))
            if confidence < _CONF_MIN_REVIEW:
                continue

            raw_key = str(item.get("topic_key", item.get("topic", query))).strip()
            topic_key = self._slugify(raw_key)
            if not topic_key:
                continue
            topic_title = str(item.get("topic", topic_key.replace("_", " ").title())).strip()
            subtopics = [
                str(s).strip().lower()
                for s in (item.get("subtopics", []) or [])
                if str(s).strip()
            ]

            fact_id, status = self.merge_fact(
                topic_key,
                topic_title,
                claim,
                confidence=confidence,
                source="web_research",
                source_file=source_file,
                project=project,
                subtopics=subtopics,
                ollama_client=ollama_client,
            )

            if fact_id:
                topics_touched.add(topic_key)
                if confidence >= _CONF_AUTO_CANON:
                    canon_added += 1
                else:
                    rev_id = self.create_pending_review(
                        topic_key,
                        fact_id,
                        claim,
                        confidence=confidence,
                        source="web_research",
                        source_file=source_file,
                        project=project,
                    )
                    if rev_id:
                        reviews_created += 1

        return {
            "topics_touched": sorted(topics_touched),
            "canon_added": canon_added,
            "reviews_created": reviews_created,
        }

    def merge_fact(
        self,
        topic_key: str,
        title: str,
        claim: str,
        *,
        confidence: float,
        source: str,
        source_file: str,
        project: str,
        subtopics: list[str] | None = None,
        ollama_client: Any = None,
    ) -> tuple[str, str]:
        """
        Add or update a fact in the topic file.
        Returns (fact_id, status) or ("", "") if duplicate/skipped.
        status is "canon" if confidence >= threshold, else "flagged".
        """
        claim = claim.strip()[:500]
        if not claim or not topic_key:
            return ("", "")

        status = "canon" if confidence >= _CONF_AUTO_CANON else "flagged"
        now = _now_iso()

        with self.lock:
            topic = self._load_topic(topic_key)
            if not topic.get("key"):
                topic = {
                    "key": topic_key,
                    "title": title or topic_key.replace("_", " ").title(),
                    "summary": "",
                    "facts": [],
                    "subtopics": [],
                    "related_topics": [],
                    "created_at": now,
                    "updated_at": now,
                }

            # Deduplication — token overlap first (fast, no LLM call)
            for existing in topic.get("facts", []):
                existing_claim = str(existing.get("claim", ""))
                if _token_overlap(claim, existing_claim) >= _SIMILARITY_THRESHOLD:
                    if confidence > float(existing.get("confidence", 0.0)):
                        existing["confidence"] = round(confidence, 4)
                        existing["updated_at"] = now
                        if confidence >= _CONF_AUTO_CANON:
                            existing["status"] = "canon"
                        topic["updated_at"] = now
                        self._save_topic(topic)
                    return (str(existing.get("id", "")), str(existing.get("status", status)))

            # Semantic dedup fallback — catches paraphrase duplicates Jaccard missed
            if ollama_client is not None:
                try:
                    new_vec = ollama_client.embed("qwen3-embedding:4b", claim[:2000])
                    for existing in topic.get("facts", []):
                        existing_claim = str(existing.get("claim", ""))
                        existing_vec = ollama_client.embed("qwen3-embedding:4b", existing_claim[:2000])
                        if _vec_cosine(new_vec, existing_vec) >= 0.88:
                            if confidence > float(existing.get("confidence", 0.0)):
                                existing["confidence"] = round(confidence, 4)
                                existing["updated_at"] = now
                                if confidence >= _CONF_AUTO_CANON:
                                    existing["status"] = "canon"
                                topic["updated_at"] = now
                                self._save_topic(topic)
                            return (str(existing.get("id", "")), str(existing.get("status", status)))
                except Exception:
                    pass

            fact_id = "f_" + uuid.uuid4().hex[:10]
            fact: dict[str, Any] = {
                "id": fact_id,
                "claim": claim,
                "confidence": round(confidence, 4),
                "source": source,
                "source_file": source_file,
                "project": project,
                "status": status,
                "votes": {"up": 0, "down": 0},
                "created_at": now,
                "updated_at": now,
            }
            topic.setdefault("facts", []).append(fact)

            # Merge subtopics
            existing_subs = set(topic.get("subtopics", []))
            for s in (subtopics or []):
                existing_subs.add(s)
            topic["subtopics"] = sorted(existing_subs)[:20]

            # Update title if we have a better one
            if title and topic.get("title", "").lower() == topic_key.replace("_", " "):
                topic["title"] = title

            topic["updated_at"] = now
            self._save_topic(topic)

        return (fact_id, status)

    def create_pending_review(
        self,
        topic_key: str,
        fact_id: str,
        claim: str,
        *,
        confidence: float,
        source: str,
        source_file: str,
        project: str,
    ) -> str:
        """Create a review item in topic_reviews.json. Returns review_id."""
        rev_id = "rev_" + uuid.uuid4().hex[:10]
        now = _now_iso()
        claim_short = claim[:200]
        question = f'Did Oathweaver get this right? "{claim_short}"'

        with self.lock:
            data = self._load_reviews()
            data.setdefault("reviews", []).append({
                "id": rev_id,
                "status": "pending",
                "topic_key": topic_key,
                "fact_id": fact_id,
                "question": question,
                "claim": claim_short,
                "source": source,
                "source_file": source_file,
                "project": project,
                "confidence": round(confidence, 4),
                "created_at": now,
                "answered_at": "",
                "answer": "",
            })
            self._save_reviews(data)
        return rev_id

    def answer_review(self, review_id: str, accepted: bool) -> bool:
        """
        Handle user yes/no answer.
        accepted=True  → fact status → "canon"
        accepted=False → fact status → "rejected"
        Returns True on success.
        """
        now = _now_iso()
        with self.lock:
            # Update review record
            reviews_data = self._load_reviews()
            review: dict[str, Any] | None = None
            for rev in reviews_data.get("reviews", []):
                if rev.get("id") == review_id:
                    review = rev
                    break
            if review is None:
                return False

            review["status"] = "accepted" if accepted else "rejected"
            review["answer"] = "yes" if accepted else "no"
            review["answered_at"] = now
            self._save_reviews(reviews_data)

            # Update the fact in its topic file
            topic_key = str(review.get("topic_key", "")).strip()
            fact_id = str(review.get("fact_id", "")).strip()
            if topic_key and fact_id:
                topic = self._load_topic(topic_key)
                for fact in topic.get("facts", []):
                    if fact.get("id") == fact_id:
                        fact["status"] = "canon" if accepted else "rejected"
                        fact["updated_at"] = now
                        topic["updated_at"] = now
                        break
                if topic.get("key"):
                    self._save_topic(topic)

        return True

    def list_pending_reviews(self) -> list[dict[str, Any]]:
        """Return pending reviews formatted for the Postbag overlay."""
        data = self._load_reviews()
        return [
            rev for rev in data.get("reviews", [])
            if rev.get("status") == "pending"
        ]

    def get_topic(self, topic_key: str) -> dict[str, Any] | None:
        topic = self._load_topic(self._slugify(topic_key))
        return topic if topic.get("key") else None

    def list_topics(self) -> list[dict[str, Any]]:
        """Return index entries sorted by updated_at descending."""
        index = _load_json(self.index_path, {"topics": {}})
        entries = list(index.get("topics", {}).values())
        entries.sort(key=lambda x: str(x.get("updated_at", "")), reverse=True)
        return entries

    def get_context_for_query(self, query: str, max_facts: int = _MAX_FACTS_INJECT) -> str:
        """
        Keyword-match query against topic_index, return compact canon facts string.
        Returns "" if no relevant topics found.
        """
        if not query or not query.strip():
            return ""

        query_tokens = set(re.findall(r"\w+", query.lower()))
        if len(query_tokens) < 2:
            return ""

        index = _load_json(self.index_path, {"topics": {}})
        topic_dict = index.get("topics", {})

        scored: list[tuple[float, str]] = []

        # Try semantic scoring first
        query_vec = self._try_embed(query[:2000])
        if query_vec is not None:
            for key, meta in topic_dict.items():
                if not meta.get("canon_count", 0):
                    continue
                topic_text = " ".join([
                    str(meta.get("title", "")),
                    " ".join(meta.get("subtopics", [])),
                ])
                topic_vec = self._try_embed(topic_text[:2000])
                if topic_vec is None:
                    continue
                sim = _vec_cosine(query_vec, topic_vec)
                if sim >= 0.30:
                    scored.append((sim, key))

        # Fall back to token overlap if semantic scoring yielded nothing
        if not scored:
            for key, meta in topic_dict.items():
                if not meta.get("canon_count", 0):
                    continue
                target = " ".join([
                    key,
                    str(meta.get("title", "")),
                    " ".join(meta.get("subtopics", [])),
                ])
                target_tokens = set(re.findall(r"\w+", target.lower()))
                overlap = len(query_tokens & target_tokens)
                if overlap >= 1:
                    scored.append((float(overlap), key))

        if not scored:
            return ""

        scored.sort(key=lambda x: x[0], reverse=True)
        collected: list[str] = []
        for _, key in scored[:4]:  # top 4 matching topics
            if len(collected) >= max_facts:
                break
            topic = self._load_topic(key)
            canon_facts = [
                f for f in topic.get("facts", [])
                if f.get("status") == "canon"
            ]
            # Sort by confidence
            canon_facts.sort(key=lambda f: float(f.get("confidence", 0)), reverse=True)
            title = str(topic.get("title", key)).strip()
            for fact in canon_facts[: max(1, max_facts - len(collected))]:
                claim = str(fact.get("claim", "")).strip()
                if claim:
                    claim = claim[:_MAX_CLAIM_CHARS]
                    collected.append(f"- [{title}] {claim}")
            if len(collected) >= max_facts:
                break

        if not collected:
            return ""

        return "Known facts from memory:\n" + "\n".join(collected)

    # ── Private helpers ───────────────────────────────────────────────────

    def _try_embed(self, text: str) -> list[float] | None:
        """Embed text with qwen3-embedding:4b. Returns None on any failure. Session-cached."""
        cached = self._embed_cache.get(text)
        if cached is not None:
            return cached
        try:
            from shared_tools.ollama_client import OllamaClient
            vec = OllamaClient().embed("qwen3-embedding:4b", text)
            self._embed_cache[text] = vec
            return vec
        except Exception:
            return None

    def _call_ollama_extract(
        self,
        query: str,
        sources: list[dict[str, Any]],
        ollama_client: Any,
        model_cfg: dict[str, Any],
    ) -> list[dict[str, Any]] | None:
        model = str(model_cfg.get("model", "")).strip()
        if not model:
            return None

        # Build source snippets
        snippets: list[str] = []
        for src in sources[:_MAX_SOURCES_FOR_EXTRACT]:
            title = str(src.get("title", "")).strip()
            snippet = str(src.get("snippet", "")).strip()[:600]
            domain = str(src.get("source_domain", "")).strip()
            if snippet:
                snippets.append(f"[{domain}] {title}: {snippet}")

        if not snippets:
            return None

        system_prompt = (
            "You are a fact extractor. Given research sources about a query, "
            "extract factual claims. Return a JSON array only, no prose, no markdown fences:\n"
            '[\n  {\n    "topic": "Human-readable topic name",\n'
            '    "topic_key": "snake_case_key_max_5_words",\n'
            '    "claim": "One specific factual sentence, max 120 chars.",\n'
            '    "confidence": 0.0_to_1.0,\n'
            '    "subtopics": ["keyword1", "keyword2"]\n  }\n]\n'
            "Aim for 3-8 claims total across 1-3 topics. "
            "Confidence guide: 0.9=well-cited by tier-1 source, 0.75=likely true from multiple sources, "
            "0.65=uncertain or single source. Only include claims ≥ 0.60. "
            "topic_key must be lowercase with underscores, max 5 words (e.g. dog_nutrition)."
        )
        user_prompt = f"Query: {query}\n\nSources:\n" + "\n\n".join(snippets)

        try:
            raw = ollama_client.chat(
                model=model,
                system_prompt=system_prompt,
                user_prompt=user_prompt,
                temperature=float(model_cfg.get("temperature", 0.1)),
                num_ctx=int(model_cfg.get("num_ctx", 8192)),
                think=False,
                timeout=120,
            )
        except Exception:
            return None

        # Parse JSON from response
        raw = str(raw or "").strip()
        # Strip markdown fences if present
        raw = re.sub(r"^```(?:json)?\s*", "", raw, flags=re.MULTILINE)
        raw = re.sub(r"\s*```$", "", raw, flags=re.MULTILINE)
        # Find first [...] block
        m = re.search(r"\[.*\]", raw, re.DOTALL)
        if not m:
            return None
        try:
            parsed = json.loads(m.group(0))
            if not isinstance(parsed, list):
                return None
            result: list[dict[str, Any]] = []
            for item in parsed:
                if not isinstance(item, dict):
                    continue
                claim = str(item.get("claim", "")).strip()
                if not claim:
                    continue
                try:
                    conf = float(item.get("confidence", 0.0))
                except (TypeError, ValueError):
                    conf = 0.0
                result.append({
                    "topic": str(item.get("topic", "")).strip(),
                    "topic_key": str(item.get("topic_key", "")).strip(),
                    "claim": claim,
                    "confidence": max(0.0, min(1.0, conf)),
                    "subtopics": [
                        str(s).strip().lower()
                        for s in (item.get("subtopics", []) or [])
                        if str(s).strip()
                    ],
                })
            return result if result else None
        except (json.JSONDecodeError, ValueError):
            return None

    def _heuristic_extract(
        self, query: str, sources: list[dict[str, Any]]
    ) -> list[dict[str, Any]]:
        """
        Fallback: one claim per unique source domain, confidence 0.62.
        All claims are attributed to a single topic derived from the query.
        """
        topic_key = self._slugify(query)[:32]
        topic_title = query.strip().title()[:64]
        seen_domains: set[str] = set()
        result: list[dict[str, Any]] = []

        for src in sources[:6]:
            domain = str(src.get("source_domain", "")).strip()
            snippet = str(src.get("snippet", "")).strip()[:200]
            if not snippet or domain in seen_domains:
                continue
            seen_domains.add(domain)
            # Trim snippet to a sentence
            sentence = re.split(r"[.!?]", snippet)[0].strip()
            if len(sentence) < 20:
                sentence = snippet[:120].strip()
            if not sentence:
                continue
            result.append({
                "topic": topic_title,
                "topic_key": topic_key,
                "claim": sentence,
                "confidence": 0.62,
                "subtopics": [],
            })

        return result

    def _load_topic(self, key: str) -> dict[str, Any]:
        path = self.topics_dir / f"{key}.json"
        return _load_json(path, {})

    def _save_topic(self, data: dict[str, Any]) -> None:
        key = str(data.get("key", "")).strip()
        if not key:
            return
        path = self.topics_dir / f"{key}.json"
        _atomic_write(path, data)
        self._update_index(key, data)

    def _update_index(self, key: str, data: dict[str, Any]) -> None:
        index = _load_json(self.index_path, {"topics": {}})
        facts = data.get("facts", [])
        canon_count = sum(1 for f in facts if f.get("status") == "canon")
        index.setdefault("topics", {})[key] = {
            "key": key,
            "title": str(data.get("title", key)).strip(),
            "subtopics": data.get("subtopics", [])[:10],
            "fact_count": len(facts),
            "canon_count": canon_count,
            "updated_at": data.get("updated_at", _now_iso()),
        }
        _atomic_write(self.index_path, index)

    def _load_reviews(self) -> dict[str, Any]:
        return _load_json(self.reviews_path, {"reviews": []})

    def _save_reviews(self, data: dict[str, Any]) -> None:
        _atomic_write(self.reviews_path, data)

    def _slugify(self, text: str) -> str:
        text = str(text or "").strip().lower()
        text = re.sub(r"[^a-z0-9\s_]", " ", text)
        text = re.sub(r"\s+", "_", text.strip())
        text = re.sub(r"_+", "_", text).strip("_")
        return text[:48] or "general"
