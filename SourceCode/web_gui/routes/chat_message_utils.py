from __future__ import annotations

import json as _json
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from shared_tools.web_research import build_web_progress_payload


def normalize_lora_selection(raw: Any) -> list[str]:
    values = raw if isinstance(raw, list) else []
    seen: set[str] = set()
    out: list[str] = []
    for item in values:
        text = str(item or "").strip()
        if not text or text in seen:
            continue
        seen.add(text)
        out.append(text[:220])
        if len(out) >= 32:
            break
    return out


def parse_selected_loras_value(raw: Any) -> list[str]:
    if isinstance(raw, list):
        return normalize_lora_selection(raw)
    text = str(raw or "").strip()
    if not text:
        return []
    if text.startswith("["):
        try:
            payload = _json.loads(text)
            if isinstance(payload, list):
                return normalize_lora_selection(payload)
        except Exception:
            return []
        return []
    return normalize_lora_selection([part.strip() for part in text.split(",") if part.strip()])


def to_bool(raw: Any, *, default: bool = False) -> bool:
    if raw is None:
        return default
    if isinstance(raw, bool):
        return raw
    text = str(raw).strip().lower()
    if not text:
        return default
    if text in {"1", "true", "yes", "on"}:
        return True
    if text in {"0", "false", "no", "off"}:
        return False
    return default


def to_int(raw: Any, *, default: int | None = None) -> int | None:
    if raw is None:
        return default
    text = str(raw).strip()
    if not text:
        return default
    try:
        return int(text)
    except (TypeError, ValueError):
        return default


def to_float(raw: Any, *, default: float | None = None) -> float | None:
    if raw is None:
        return default
    text = str(raw).strip()
    if not text:
        return default
    try:
        return float(text)
    except (TypeError, ValueError):
        return default


def normalize_message_web_sources(raw_sources: Any) -> list[dict[str, Any]]:
    rows = raw_sources if isinstance(raw_sources, list) else []
    out: list[dict[str, Any]] = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        url = str(row.get("url") or row.get("source_url") or row.get("link") or "").strip()
        domain = str(row.get("domain") or row.get("source_domain") or row.get("host") or "").strip().lower()
        title = str(row.get("title") or "").strip()
        tier = str(row.get("tier") or row.get("source_tier") or "").strip()
        try:
            score = float(row.get("score", row.get("source_score", 0.0)) or 0.0)
        except (TypeError, ValueError):
            score = 0.0
        if not url and not domain:
            continue
        out.append(
            {
                "url": url,
                "domain": domain,
                "title": title,
                "tier": tier,
                "score": score,
            }
        )
    return out


def build_message_web_meta(
    *,
    web_stack: Any = None,
    web_details: Any = None,
    research_reply: Any = None,
    think_stream: Any = None,
) -> dict[str, Any] | None:
    stack = dict(web_stack) if isinstance(web_stack, dict) else {}
    details = dict(web_details) if isinstance(web_details, dict) else {}
    research = dict(research_reply) if isinstance(research_reply, dict) else {}
    if details and not stack:
        stack = build_web_progress_payload(details)
    detail_sources = normalize_message_web_sources(details.get("sources"))
    if detail_sources:
        stack["web_sources"] = detail_sources
        stack["source_count"] = max(int(stack.get("source_count", 0) or 0), len(detail_sources))
    else:
        stack["web_sources"] = normalize_message_web_sources(stack.get("web_sources"))
    if not stack.get("web_sources"):
        stack.pop("web_sources", None)
    stream = dict(think_stream) if isinstance(think_stream, dict) else {}
    if not stack and not research and not stream:
        return None
    payload: dict[str, Any] = {}
    if stack:
        payload["web_sources"] = list(stack.get("web_sources") or [])
        payload["web_stack"] = stack
    if research:
        payload["research_reply"] = {
            "type": "research_reply",
            "text": str(research.get("text", "")),
            "sentences": [dict(x) for x in (research.get("sentences") or []) if isinstance(x, dict)],
            "retrieved_chunks": [dict(x) for x in (research.get("retrieved_chunks") or []) if isinstance(x, dict)],
        }
    if stream:
        payload["think_stream"] = stream
    return payload


def build_message_think_stream(job_row: Any, *, expiry_hours: int = 48) -> dict[str, Any] | None:
    row = dict(job_row) if isinstance(job_row, dict) else {}
    events = row.get("events")
    if not isinstance(events, list) or not events:
        return None
    clean_events: list[dict[str, str]] = []
    for item in events[-48:]:
        if not isinstance(item, dict):
            continue
        ts = str(item.get("ts", "")).strip()
        stage = str(item.get("stage", "")).strip()
        detail = str(item.get("detail", "")).strip()
        if not ts and not stage and not detail:
            continue
        clean_events.append(
            {
                "ts": ts,
                "stage": stage,
                "detail": detail[:400],
            }
        )
    if not clean_events:
        return None
    started_at = str(row.get("started_at", "")).strip() or clean_events[0].get("ts", "")
    ended_at = str(row.get("updated_at", "")).strip() or clean_events[-1].get("ts", "")
    started_ms = 0.0
    ended_ms = 0.0
    try:
        if started_at:
            started_ms = datetime.fromisoformat(started_at.replace("Z", "+00:00")).timestamp()
    except Exception:
        started_ms = 0.0
    try:
        if ended_at:
            ended_ms = datetime.fromisoformat(ended_at.replace("Z", "+00:00")).timestamp()
    except Exception:
        ended_ms = 0.0
    duration_sec = max(0.0, ended_ms - started_ms) if started_ms > 0 and ended_ms >= started_ms else 0.0
    expires_at = (datetime.now(timezone.utc) + timedelta(hours=max(1, int(expiry_hours)))).isoformat()
    return {
        "events": clean_events,
        "started_at": started_at,
        "ended_at": ended_at,
        "duration_sec": float(f"{duration_sec:.3f}"),
        "expires_at": expires_at,
    }


def read_optional_text(path_text: str, *, repo_root: Path) -> str:
    raw = str(path_text or "").strip()
    if not raw:
        return ""
    try:
        path = Path(raw)
    except Exception:
        return ""
    if not path.is_absolute():
        path = repo_root / path
    try:
        if not path.exists() or not path.is_file():
            return ""
        return path.read_text(encoding="utf-8", errors="ignore")
    except Exception:
        return ""


def truncate_utf8(text: str, limit_bytes: int) -> str:
    if limit_bytes <= 0:
        return ""
    raw = str(text or "")
    blob = raw.encode("utf-8", errors="ignore")
    if len(blob) <= limit_bytes:
        return raw
    return blob[:limit_bytes].decode("utf-8", errors="ignore")

