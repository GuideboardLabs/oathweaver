from __future__ import annotations

import json as _json
import logging
import re
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import TYPE_CHECKING, Any

from flask import Blueprint, abort, jsonify, request

from shared_tools.content_guardrails import check_content
from shared_tools.web_research import build_web_progress_payload
from web_gui.chat_helpers import bg_retitle, bg_summarize, handle_command
from web_gui.utils.file_utils import normalize_project_slug as _normalize_project_slug
from web_gui.utils.history_builders import (
    build_command_history as _build_command_history,
    build_fact_history as _build_fact_history,
    build_talk_history as _build_talk_history,
    extract_talk_text as _extract_talk_text,
)

if TYPE_CHECKING:
    from web_gui.app_context import AppContext


LOGGER = logging.getLogger(__name__)

_IMAGE_REF_TOKEN_RE = re.compile(r"\{image\s*\d+\}", re.IGNORECASE)
_NIGHT_SCENE_RE = re.compile(r"\b(night|dark)\b", re.IGNORECASE)
_RELATION_SCENE_RE = re.compile(r"\b(at the bottom of|in front of|behind|foreground|background)\b", re.IGNORECASE)
_FIRE_RE = re.compile(r"\b(on fire|burning|ablaze|in flames|flames)\b", re.IGNORECASE)
_SUBJECT_ENTITY_RE = re.compile(
    r"\b("
    r"person|people|human|man|woman|child|hero|warrior|creature|animal|dragon|fox|wolf|cat|dog|bird|"
    r"fortress|castle|citadel|keep|building|house|tower|bridge|ship|boat|vehicle|car|train|robot|monster"
    r")\b",
    re.IGNORECASE,
)
_SETTING_ENTITY_RE = re.compile(
    r"\b("
    r"landscape|mountain|mountains|mountain pass|valley|forest|meadow|field|desert|coast|shore|sea|ocean|"
    r"river|city|town|village|street|sky|horizon|snow|snowy|background|foreground|midground"
    r")\b",
    re.IGNORECASE,
)
_TRAILING_ASSISTANT_RULE_RE = re.compile(r"(?:\n\s*\*\*\*\s*)+\Z", re.MULTILINE)


def _strip_trailing_assistant_rule(text: str) -> str:
    raw = str(text or "").rstrip()
    if not raw:
        return ""
    return _TRAILING_ASSISTANT_RULE_RE.sub("", raw).rstrip()


def _normalize_lora_selection(raw: Any) -> list[str]:
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


def _parse_selected_loras_value(raw: Any) -> list[str]:
    if isinstance(raw, list):
        return _normalize_lora_selection(raw)
    text = str(raw or "").strip()
    if not text:
        return []
    if text.startswith("["):
        try:
            payload = _json.loads(text)
            if isinstance(payload, list):
                return _normalize_lora_selection(payload)
        except Exception:
            return []
        return []
    return _normalize_lora_selection([part.strip() for part in text.split(",") if part.strip()])


def _to_bool(raw: Any, *, default: bool = False) -> bool:
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


def _to_int(raw: Any, *, default: int | None = None) -> int | None:
    if raw is None:
        return default
    text = str(raw).strip()
    if not text:
        return default
    try:
        return int(text)
    except (TypeError, ValueError):
        return default


def _to_float(raw: Any, *, default: float | None = None) -> float | None:
    if raw is None:
        return default
    text = str(raw).strip()
    if not text:
        return default
    try:
        return float(text)
    except (TypeError, ValueError):
        return default


def _normalize_message_web_sources(raw_sources: Any) -> list[dict[str, Any]]:
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
        out.append({
            "url": url,
            "domain": domain,
            "title": title,
            "tier": tier,
            "score": score,
        })
    return out


def _build_message_web_meta(
    *,
    web_stack: Any = None,
    web_details: Any = None,
    research_reply: Any = None,
) -> dict[str, Any] | None:
    stack = dict(web_stack) if isinstance(web_stack, dict) else {}
    details = dict(web_details) if isinstance(web_details, dict) else {}
    research = dict(research_reply) if isinstance(research_reply, dict) else {}
    if details and not stack:
        stack = build_web_progress_payload(details)
    detail_sources = _normalize_message_web_sources(details.get("sources"))
    if detail_sources:
        stack["web_sources"] = detail_sources
        stack["source_count"] = max(int(stack.get("source_count", 0) or 0), len(detail_sources))
    else:
        stack["web_sources"] = _normalize_message_web_sources(stack.get("web_sources"))
    if not stack.get("web_sources"):
        stack.pop("web_sources", None)
    if not stack and not research:
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
    return payload


def _read_optional_text(path_text: str, *, repo_root: Path) -> str:
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


def _truncate_utf8(text: str, limit_bytes: int) -> str:
    if limit_bytes <= 0:
        return ""
    raw = str(text or "")
    blob = raw.encode("utf-8", errors="ignore")
    if len(blob) <= limit_bytes:
        return raw
    return blob[:limit_bytes].decode("utf-8", errors="ignore")


def _make_output_row_for_request_id(orch: Any, project_slug: str, extends_request_id: str) -> dict[str, Any] | None:
    rid = str(extends_request_id or "").strip()
    if not rid:
        return None
    rows = orch.activity_store.rows() if hasattr(orch, "activity_store") else []
    if not isinstance(rows, list):
        return None
    if rid.startswith("activity:"):
        try:
            idx = int(rid.split(":", 1)[1].strip())
        except (TypeError, ValueError):
            idx = -1
        if 0 <= idx < len(rows):
            row = rows[idx] if isinstance(rows[idx], dict) else None
            if not isinstance(row, dict):
                return None
            details = row.get("details") if isinstance(row.get("details"), dict) else {}
            if str(details.get("project", "")).strip() == project_slug and str(row.get("event", "")).strip() == "make_deliverable_written":
                return row
        return None
    for row in rows:
        if not isinstance(row, dict):
            continue
        details = row.get("details")
        if not isinstance(details, dict):
            continue
        if str(details.get("project", "")).strip() != project_slug:
            continue
        if str(row.get("event", "")).strip() != "make_deliverable_written":
            continue
        if str(details.get("request_id", "")).strip() == rid:
            return row
    return None


def _seed_artifact_text_for_extension(orch: Any, project_slug: str, extends_request_id: str) -> str:
    row = _make_output_row_for_request_id(orch, project_slug, extends_request_id)
    if not isinstance(row, dict):
        return ""
    details = row.get("details")
    if not isinstance(details, dict):
        return ""
    summary_path = str(details.get("summary_path") or details.get("path") or "").strip()
    raw_path = str(details.get("raw_path") or "").strip()
    repo_root = getattr(orch, "repo_root", Path.cwd())
    summary_text = _read_optional_text(summary_path, repo_root=repo_root)
    raw_text = _read_optional_text(raw_path, repo_root=repo_root)
    if not raw_text and summary_path:
        try:
            summary_file = Path(summary_path)
            sidecar = summary_file.with_name(f"{summary_file.stem}_raw.md")
            raw_text = _read_optional_text(str(sidecar), repo_root=repo_root)
        except Exception:
            raw_text = ""
    if not summary_text and not raw_text:
        return ""

    cap = 80 * 1024
    summary_blob = summary_text.encode("utf-8", errors="ignore")
    raw_blob = raw_text.encode("utf-8", errors="ignore")
    if len(summary_blob) > cap:
        summary_text = _truncate_utf8(summary_text, cap)
        raw_text = ""
    elif len(summary_blob) + len(raw_blob) > cap:
        raw_budget = max(0, cap - len(summary_blob))
        raw_text = _truncate_utf8(raw_text, raw_budget)

    seed_lines = [
        "Prior output to extend (continue, refine, or extend — do not start from scratch):",
        "",
        summary_text.strip() if summary_text.strip() else "(No prior summary text found.)",
    ]
    raw_clean = raw_text.strip()
    if raw_clean:
        seed_lines.extend(["", "--- raw output ---", "", raw_clean])
    return "\n".join(seed_lines).strip()


def _is_simple_image_prompt(prompt: str) -> bool:
    text = " ".join(str(prompt or "").strip().split())
    if not text:
        return False
    words = [w for w in re.split(r"\s+", text) if w]
    if len(words) <= 7:
        return True
    if len(words) <= 12 and "," not in text and "." not in text and ":" not in text:
        return True
    return False


def _has_structured_scene_request(prompt: str) -> bool:
    text = " ".join(str(prompt or "").strip().split())
    if not text:
        return False
    if _RELATION_SCENE_RE.search(text):
        return True
    has_subject = bool(_SUBJECT_ENTITY_RE.search(text))
    has_setting = bool(_SETTING_ENTITY_RE.search(text))
    return has_subject and has_setting


def _canonical_entity_name(raw: str) -> str:
    token = str(raw or "").strip().lower()
    if token in {"castle", "citadel", "keep"}:
        return "fortress"
    if token in {"people", "human", "man", "woman", "child", "hero", "warrior"}:
        return "person"
    if token in {"animal", "dragon", "fox", "wolf", "cat", "dog", "bird", "monster"}:
        return "creature"
    if token in {"boat"}:
        return "ship"
    if token in {"vehicle"}:
        return "car"
    return token


def _extract_required_entities(prompt: str, *, max_items: int = 6) -> list[str]:
    text = " ".join(str(prompt or "").strip().split())
    if not text:
        return []
    out: list[str] = []
    seen: set[str] = set()
    for match in _SUBJECT_ENTITY_RE.finditer(text):
        name = _canonical_entity_name(match.group(0))
        if not name or name in seen:
            continue
        seen.add(name)
        out.append(name)
        if len(out) >= max_items:
            break
    if _FIRE_RE.search(text) and "fire" not in seen and len(out) < max_items:
        out.append("fire")
    return out


def _extract_required_conditions(prompt: str, *, max_items: int = 6) -> list[str]:
    text = " ".join(str(prompt or "").strip().split()).lower()
    if not text:
        return []

    conditions: list[str] = []
    seen: set[str] = set()

    def _push(value: str) -> None:
        key = str(value or "").strip().lower()
        if not key or key in seen:
            return
        seen.add(key)
        conditions.append(value.strip())

    if _FIRE_RE.search(text):
        _push("requested fire is explicit with visible flames and smoke")

    # Generic condition pairing: if a known subject entity appears near fire terms,
    # force that subject's state to be explicit in-frame.
    for match in _SUBJECT_ENTITY_RE.finditer(text):
        entity = _canonical_entity_name(match.group(0))
        if not entity:
            continue
        start, end = match.span()
        near_after = text[end:min(len(text), end + 48)]
        near_before = text[max(0, start - 48):start]
        if _FIRE_RE.search(near_after) or _FIRE_RE.search(near_before):
            _push(f"{entity} is visibly on fire with active flames and smoke")
        if len(conditions) >= max_items:
            break

    return conditions[:max_items]


def _scene_guidance_extras(prompt: str) -> list[str]:
    text = " ".join(str(prompt or "").strip().split())
    has_structured_scene = _has_structured_scene_request(text)
    required_entities = _extract_required_entities(text)
    required_conditions = _extract_required_conditions(text)
    if not has_structured_scene and not required_entities and not required_conditions:
        return []

    extras: list[str] = [
        "single coherent composition where requested elements and environment coexist in one frame",
        "all explicitly requested elements must be clearly visible and recognizable",
        "do not omit, replace, or minimize key requested elements",
    ]
    if required_entities:
        extras.append(f"required visible elements: {', '.join(required_entities)}")
    if required_conditions:
        extras.append(f"required conditions: {'; '.join(required_conditions)}")
        extras.append("required conditions must be literal and clearly visible, not implied")
    if has_structured_scene:
        extras.extend([
            "maintain clear foreground, midground, and background separation",
            "avoid detached split-scene composition",
        ])
    if "fire" in required_entities:
        extras.append("if fire is requested, flames and smoke must be clearly visible on the requested subject")
    return extras


def _merge_negative_prompt_terms(base_negative_prompt: str, extras: list[str]) -> str:
    merged: list[str] = []
    seen: set[str] = set()

    def _append(raw: str) -> None:
        text = str(raw or "").strip()
        if not text:
            return
        key = text.lower()
        if key in seen:
            return
        seen.add(key)
        merged.append(text)

    for chunk in re.split(r"[,\n;]+", str(base_negative_prompt or "")):
        _append(chunk)
    for chunk in extras:
        _append(chunk)
    return ", ".join(merged)


def _refine_negative_prompt(
    negative_prompt: str,
    *,
    prompt: str,
    preset_id: str = "",
) -> str:
    text = " ".join(str(prompt or "").strip().split())
    if not text:
        return str(negative_prompt or "").strip()
    has_structured_scene = _has_structured_scene_request(text)
    required_entities = _extract_required_entities(text)
    required_conditions = _extract_required_conditions(text)
    if not has_structured_scene and not required_entities and not required_conditions:
        return str(negative_prompt or "").strip()

    extras = [
        "split screen",
        "diptych",
        "triptych",
        "collage",
        "comic panel",
        "multi frame",
        "subject omitted",
        "tiny distant subject",
        "out of frame subject",
        "empty landscape",
        "detached foreground/background",
        "substituted subject",
    ]
    extras.extend([f"missing {name}" for name in required_entities if name and name != "fire"])
    if "fire" in required_entities:
        extras.extend([
            "flames not visible",
            "smoke not visible",
            "unlit subject",
            "fire only implied",
        ])
    extras.extend([f"missing condition: {item}" for item in required_conditions if str(item).strip()])

    preset_key = str(preset_id or "").strip().lower()
    _pony_presets = {"and_the_hound", "borderfox", "uwu_figurine", "painterly", "realism", "fixel", "pastels", "unfinished_anime"}
    _strict_animal_presets = {"and_the_hound", "fixel"}
    # Presets that must never produce furry/pony/cartoon source output regardless of subject
    _antifurry_presets = {"pastels", "unfinished_anime"}
    if preset_key in _pony_presets and _pony_is_human_subject(text):
        extras.extend(_PONY_HYBRID_NEGATIVES)
    elif preset_key in _strict_animal_presets and bool(_PONY_ANIMAL_RE.search(text)):
        # Animal subject in a Pony preset — lock out anthro drift from both directions
        extras.extend(_PONY_HYBRID_NEGATIVES)
        extras.extend(["humanoid", "bipedal", "standing upright", "human hands", "human feet", "clothed animal"])
        extras.extend(_PONY_ANIMAL_NSFW_NEGATIVES)
    if preset_key in _antifurry_presets:
        extras.extend(_PONY_SOURCE_ANTIFURRY_NEGATIVES)
    return _merge_negative_prompt_terms(negative_prompt, extras)


_PONY_ANIMAL_RE = re.compile(
    r"\b(dog|cat|fox|wolf|bear|rabbit|bunny|deer|horse|dragon|lion|tiger|bird|owl|raccoon|"
    r"snake|lizard|shark|fish|feline|canine|pony|mare|stallion|beast|creature|monster|"
    r"animal|fur|furry|kemono|anthro)\b",
    re.IGNORECASE,
)
_PONY_HUMAN_RE = re.compile(
    r"\b(human|person|man|woman|girl|boy|lady|gentleman|warrior|wizard|princess|prince|"
    r"knight|mage|elf|dwarf|hero|villain|character|figure|portrait|face)\b",
    re.IGNORECASE,
)
_PONY_HYBRID_NEGATIVES = [
    "tail", "animal tail", "animal ears", "cat ears", "dog ears", "wolf ears", "fox ears",
    "fur", "furry", "kemono", "anthro", "animal features", "hybrid", "beast",
    "snout", "muzzle", "paws", "claws on hands", "animal nose",
]
_PONY_ANIMAL_NSFW_NEGATIVES = [
    "nsfw", "nude", "naked", "explicit", "suggestive", "sexual", "lewd", "adult content",
    "breasts", "large breasts", "huge breasts", "big breasts", "cleavage", "nipples",
    "anthro female", "anthro male", "sexy pose", "pinup",
    "rating:explicit", "rating:questionable",
]
# Pony source-tag negatives — suppress furry/pony/cartoon training data bias entirely
_PONY_SOURCE_ANTIFURRY_NEGATIVES = [
    "source_furry", "source_pony", "source_cartoon",
    "furry", "anthro", "kemono", "animal ears", "animal tail", "fur", "pony",
    "score_4", "score_5",
]


def _pony_is_human_subject(text: str) -> bool:
    """True when the prompt clearly describes a human and mentions no animals."""
    return bool(_PONY_HUMAN_RE.search(text)) and not bool(_PONY_ANIMAL_RE.search(text))


def _refine_image_prompt(
    prompt: str,
    *,
    image_style: str,
    selected_loras: list[str],
    has_references: bool,
    preset_id: str = "",
    refiner_profile: dict[str, Any] | None = None,
    scene_subject: str = "",
) -> str:
    text = " ".join(str(prompt or "").strip().split())
    subject = str(scene_subject or "").strip().lower()
    if not text:
        return text
    is_simple = _is_simple_image_prompt(text)
    scene_extras = _scene_guidance_extras(text)
    if not is_simple and not scene_extras:
        return text

    preset_key = str(preset_id or "").strip().lower()
    if preset_key == "foxo_slyesium":
        extras = [
            "masterpiece",
            "best quality",
            "8k",
            "oil painting",
            "soft lighting",
            "ZaUm",
        ]
        _people_re = re.compile(r"\b(person|people|man|woman|girl|boy|character|figure|face|portrait)\b", re.IGNORECASE)
        is_char = subject == "character" or (not subject and _people_re.search(text))
        extras.append("elysiumChar" if is_char else "elysiumScape")
        extras.extend(scene_extras)
        return f"{text}, {', '.join(extras)}"

    if preset_key == "pixel_forge":
        extras = [
            "pixel",
            "pixel art",
            "pixelated",
            "limited color palette",
            "masterpiece",
            "best quality",
        ]
        if subject == "character":
            extras.extend(["character sprite", "full body", "clean outline"])
        elif subject == "scene":
            extras.extend(["pixel art background", "tileset style", "detailed scenery"])
        else:
            extras.append("retro game style")
        extras.extend(scene_extras)
        return f"{text}, {', '.join(extras)}"

    if preset_key == "fhoxi":
        extras = [
            "chibi",
            "cute",
            "(masterpiece)",
            "(best quality)",
            "(ultra-detailed)",
        ]
        if subject == "scene":
            extras.extend(["chibi scenery", "cute environment", "whimsical background"])
        elif subject == "object":
            extras.extend(["cute item", "chibi style object", "simple background"])
        else:
            extras.extend(["(full body:1.2)", "smile", "(beautiful detailed face)", "(beautiful detailed eyes)"])
        extras.extend(scene_extras)
        return f"{text}, {', '.join(extras)}"

    if preset_key == "faceless_uwu":
        extras = [
            "anime minimalist",
            "flat color",
            "clean lines",
        ]
        if subject == "scene":
            extras.extend(["minimalist landscape", "flat background", "simple scenery"])
        elif subject == "object":
            extras.extend(["simple object", "flat illustration", "white background"])
        else:
            extras.extend(["solo", "simple background", "faceless"])
        extras.extend(scene_extras)
        return f"{text}, {', '.join(extras)}"

    if preset_key == "nutshell":
        extras = [
            "Kurzgesagt style",
            "by Kurzgesagt",
            "vector artwork",
            "2D flat illustration",
            "clean color",
            "clear boundaries",
            "bright colors",
            "high contrast",
            "tidy style",
            "sharp focus",
            "HDR",
            "fine art",
            "masterpiece",
            "best quality",
        ]
        if subject == "character":
            extras.extend(["illustrated character", "expressive pose", "bold silhouette"])
        elif subject == "object":
            extras.extend(["product illustration", "clean white background", "icon style"])
        elif subject == "scene":
            extras.extend(["civilization", "epic landscape", "silhouette"])
        extras.extend(scene_extras)
        return f"{text}, {', '.join(extras)}"

    if preset_key == "foxs_moving_castle":
        extras = [
            "studio ghibli inspired style",
            "rich painterly textures and details",
            "cinematic composition with a clear primary focal subject",
            "single continuous scene in one frame",
            "no split-screen, no diptych, no collage, no multi-panel layout",
        ]
        if subject == "character":
            extras.extend(["character portrait", "expressive face", "soft warm lighting", "detailed clothing"])
        elif subject == "object":
            extras.extend(["detailed object", "whimsical design", "soft focus background"])
        else:
            extras.extend(["whimsical handcrafted architecture", "interior and scenery", "keep buildings and people as dominant frame elements"])
        extras.extend(scene_extras)
        night_terms = [
            str(x).strip().lower()
            for x in ((refiner_profile or {}).get("night_terms", []))
            if str(x).strip()
        ]
        night_pattern = _NIGHT_SCENE_RE if not night_terms else re.compile(
            r"\b(" + "|".join([re.escape(term) for term in night_terms]) + r")\b",
            re.IGNORECASE,
        )
        if night_pattern.search(text):
            extras.extend([
                "nighttime ambience",
                "glowing lamps and warm window light",
                "deep shadows with soft atmospheric haze",
            ])
        if has_references:
            extras.append("preserve key layout cues from reference images")
        return f"{text}, {', '.join(extras)}"

    if preset_key == "painterly":
        extras = [
            "score_9",
            "score_8_up",
            "score_7_up",
            "score_6_up",
            "score_5_up",
            "score_4_up",
            "abstractionism",
            "brush stroke",
            "traditional media",
        ]
        if subject == "scene":
            extras.extend([
                "outdoors",
                "detailed background",
                "painterly landscape",
                "expressive brushwork",
                "rich color palette",
                "atmospheric depth",
            ])
        elif subject == "object":
            extras.extend([
                "still life",
                "painterly composition",
                "expressive texture",
                "rich color",
                "dramatic lighting",
            ])
        else:
            extras.extend([
                "solo",
                "looking at viewer",
                "upper body",
                "expressive brushwork",
                "rich detail",
            ])
            if _pony_is_human_subject(text):
                extras.extend(["human", "fully human"])
        extras.extend(scene_extras)
        return f"{text}, {', '.join(extras)}"

    if preset_key == "borderfox":
        extras = [
            "score_9",
            "score_8_up",
            "score_7_up",
            "zPDXL",
            "Akaburstyle",
        ]
        if subject == "scene":
            extras.extend([
                "Akaburstyle background",
                "detailed environment",
                "painterly scenery",
                "cinematic composition",
                "dramatic lighting",
                "no characters",
            ])
        elif subject == "object":
            extras.extend([
                "Akaburstyle",
                "detailed prop",
                "stylized illustration",
                "clean composition",
                "dramatic lighting",
            ])
        else:
            extras.extend([
                "solo",
                "looking at viewer",
                "close up",
                "dramatic lighting",
                "sharp focus",
            ])
            if _pony_is_human_subject(text):
                extras.extend(["human", "fully human", "detailed face"])
            else:
                extras.extend(["detailed face", "detailed fur"])
        extras.extend(scene_extras)
        return f"{text}, {', '.join(extras)}"

    if preset_key == "uwu_figurine":
        extras = [
            "high resolution",
            "score_9",
            "score_8_up",
            "score_8",
            "figure",
        ]
        if subject == "scene":
            extras.extend(["diorama", "miniature scene", "figurine display", "detailed base", "studio lighting"])
        elif subject == "object":
            extras.extend(["prop figurine", "detailed sculpt", "clean finish", "white background", "studio lighting"])
        else:
            extras.extend(["cute", "solo", "looking at viewer", "smile", "full body", "smooth clean surface", "studio lighting", "white background"])
            if _pony_is_human_subject(text):
                extras.extend(["human", "fully human"])
        extras.extend(scene_extras)
        return f"{text}, {', '.join(extras)}"

    if preset_key == "and_the_hound":
        extras = [
            "score_9",
            "score_8_up",
            "score_7_up",
            "zPDXL",
            "DisneyRenstyle",
        ]
        if subject == "scene":
            # Landscapes/environments: Disney Renaissance painterly backgrounds
            extras.extend([
                "disney renaissance background",
                "lush detailed environment",
                "painterly scenery",
                "rich color palette",
                "cinematic composition",
                "soft atmospheric lighting",
                "no characters",
            ])
        elif subject == "object":
            # Objects: stylized props in Disney aesthetic, avoid the animal-specific anatomy negatives
            extras.extend([
                "disney renaissance style object",
                "stylized prop",
                "vibrant colors",
                "detailed illustration",
                "soft shadows",
                "clean composition",
            ])
        else:
            extras.extend([
                "expressive character",
                "vibrant colors",
                "soft warm lighting",
                "lively pose",
            ])
            if _pony_is_human_subject(text):
                extras.extend(["human", "fully human", "detailed face"])
            else:
                extras.append("detailed fur")
        extras.extend(scene_extras)
        return f"{text}, {', '.join(extras)}"

    if preset_key == "realism":
        extras = [
            "score_9",
            "score_8_up",
            "score_7_up",
            "highly detailed",
            "film grain",
        ]
        if subject == "scene":
            extras.extend(["scenery", "dynamic angle", "atmospheric depth", "natural colors", "environment"])
        elif subject == "object":
            extras.extend(["close-up", "sharp detail", "natural lighting", "film grain"])
        else:
            extras.extend(["dynamic angle", "natural lighting", "detailed skin", "sharp focus"])
            if _pony_is_human_subject(text):
                extras.extend(["human", "fully human"])
        extras.extend(scene_extras)
        return f"{text}, {', '.join(extras)}"

    if preset_key == "fixel":
        extras = [
            "score_9",
            "score_8_up",
            "score_7_up",
            "score_6_up",
            "score_5_up",
        ]
        if subject == "scene":
            extras.extend(["outdoors", "detailed background", "pixel art scenery"])
        elif subject == "object":
            extras.extend(["simple background", "centered", "product style"])
        else:
            is_human = _pony_is_human_subject(text)
            is_animal = bool(_PONY_ANIMAL_RE.search(text))
            if is_human and not is_animal:
                extras.extend(["solo", "looking at viewer", "upper body", "human", "fully human"])
            elif is_animal and not is_human:
                extras.extend([
                    "rating:safe",
                    "full body animal",
                    "quadruped",
                    "no human features",
                    "no clothing",
                    "realistic animal anatomy",
                    "wildlife photography",
                    "non-anthropomorphic",
                ])
            else:
                extras.extend(["solo", "looking at viewer", "upper body"])
        extras.extend(scene_extras)
        return f"{text}, {', '.join(extras)}"

    if preset_key == "sketch_book":
        extras = ["black and white drawing", "on white paper", "pencil sketch", "fine linework", "hand drawn"]
        if subject == "scene":
            extras.extend(["architectural detail", "cross-hatching", "ink wash"])
        elif subject == "character":
            extras.extend(["figure study", "expressive lines"])
        elif subject == "object":
            extras.extend(["still life sketch", "clean outlines"])
        extras.extend(scene_extras)
        return f"{text}, {', '.join(extras)}"

    if preset_key == "shirt_designs":
        extras = ["T shirt design", "TshirtDesignAF", "bold lineart", "fabric texture", "flat design"]
        if subject == "scene":
            extras.extend(["landscape background", "dynamic perspective"])
        elif subject == "character":
            extras.extend(["character illustration", "dynamic pose"])
        elif subject == "object":
            extras.extend(["centered object", "clean composition"])
        extras.extend(scene_extras)
        return f"{text}, {', '.join(extras)}"

    if preset_key == "wallace_vomit":
        extras = ["claymation", "stopmotion", "clay texture", "3d clay render", "soft lighting"]
        if subject == "character":
            extras.extend(["clay figure", "expressive face", "tactile surface"])
        elif subject == "scene":
            extras.extend(["miniature set", "handcrafted environment"])
        extras.extend(scene_extras)
        return f"{text}, {', '.join(extras)}"

    if preset_key == "ms_fainx":
        # Ensure trigger word is present; otherwise pass through untouched
        trigger = "MSPaint Portrait"
        if trigger.lower() not in text.lower():
            return f"{trigger} of {text}"
        return text

    if preset_key == "parchment":
        extras = [
            "on parchment",
            "illustrated",
            "annotated",
            "ink and pigment",
            "aged texture",
            "detailed linework",
            "dramatic composition",
        ]
        if subject == "scene" or not subject:
            extras.extend(["wide establishing view", "atmospheric depth"])
        elif subject == "character":
            extras.extend(["silhouette", "expressive pose", "dramatic light"])
        extras.extend(scene_extras)
        return f"{text}, {', '.join(extras)}"

    if preset_key == "foxjourney":
        extras = [
            "highly detailed",
            "intricate",
            "sharp focus",
            "dynamic lighting",
            "epic composition",
            "vibrant colors",
            "masterpiece",
            "professional digital art",
        ]
        if subject == "character":
            extras.extend(["beautiful", "expressive face", "elegant", "detailed portrait"])
        elif subject == "scene":
            extras.extend(["cinematic", "atmospheric", "rich environment", "ambient light"])
        extras.extend(scene_extras)
        return f"{text}, {', '.join(extras)}"

    if preset_key == "unfinished_anime":
        trigger = "oamhfs"
        quality_tags = "score_9, score_8_up, score_7_up, score_6_up, score_5_up, score_4_up, source_anime, screenshots"
        extras = ["anime style", "hand-drawn linework", "expressive shading", "sketch quality", "cel shaded"]
        if subject == "character":
            extras.extend(["detailed face", "expressive eyes", "dynamic pose", "monochrome"])
        elif subject == "scene":
            extras.extend(["anime background", "detailed environment", "cinematic framing"])
        elif subject == "object":
            extras.extend(["simple background", "centered", "clean lines"])
        extras.extend(scene_extras)
        has_trigger = trigger.lower() in text.lower()
        body = f"{text}, {', '.join(extras)}"
        return f"{quality_tags}, {trigger}, {body}" if not has_trigger else f"{quality_tags}, {body}"

    if preset_key == "pastels":
        trigger_phrase = "ncpy13 style pastels drawing"
        quality_tags = "score_9, score_8_up, score_7_up, score_6_up, score_5_up, score_4_up"
        extras = ["pastel colors", "soft chalk texture", "dark background", "glowing light", "painterly"]
        if subject == "scene":
            extras.extend(["atmospheric depth", "ambient light", "rich environment"])
        elif subject == "character":
            extras.extend(["expressive", "detailed face", "soft shading"])
        elif subject == "object":
            extras.extend(["centered composition", "vivid colors"])
        extras.extend(scene_extras)
        has_trigger = trigger_phrase.lower() in text.lower()
        body = f"{text}, {', '.join(extras)}, {quality_tags}"
        return f"{trigger_phrase}, {body}" if not has_trigger else body

    if preset_key == "illustration":
        # "ch" is the LoRA trigger; inject it if absent
        trigger = "ch"
        has_trigger = bool(re.search(r'\bch\b', text))
        extras = ["flat illustration", "storybook style", "colorful", "clean linework", "simple background", "graphic art"]
        if subject == "scene":
            extras.extend(["scenery", "outdoors", "sky", "cloud", "sun"])
        elif subject == "character":
            extras.extend(["solo", "expressive", "stylized figure"])
        elif subject == "object":
            extras.extend(["centered", "decorative", "white background"])
        extras.extend(scene_extras)
        body = f"{text}, {', '.join(extras)}"
        return f"{trigger}, {body}" if not has_trigger else body

    if preset_key == "foxel":
        extras = ["voxel style", "voxel art", "isometric blocks", "3d pixel art", "cubic geometry", "bright colors", "game asset", "toy-like", "clean render"]
        if subject == "character":
            extras.extend(["action figure", "blocky figure", "centered composition"])
        elif subject == "scene":
            extras.extend(["voxel environment", "isometric view", "miniature world"])
        elif subject == "object":
            extras.extend(["voxel model", "centered", "simple background"])
        extras.extend(scene_extras)
        trigger = "voxel style"
        prefix = trigger if trigger.lower() not in text.lower() else ""
        body = f"{text}, {', '.join(extras)}"
        return f"{prefix}, {body}" if prefix else body

    if preset_key == "storyboard":
        trigger = "storyboard sketch of"
        # Trigger is a prefix phrase — strip any existing variant then prepend cleanly
        stripped = text
        for variant in ("storyboard sketch of ", "storyboard sketch "):
            if stripped.lower().startswith(variant):
                stripped = stripped[len(variant):]
                break
        extras = ["storyboard sketch", "black and white", "rough pencil lines", "dynamic composition", "cinematic framing", "action lines"]
        if subject == "character":
            extras.extend(["dramatic pose", "foreshortening", "motion blur", "dutch angle"])
        elif subject == "scene":
            extras.extend(["establishing shot", "wide angle", "environmental detail"])
        elif subject == "object":
            extras.extend(["centered composition", "bold outlines"])
        extras.extend(scene_extras)
        return f"{trigger} {stripped}, {', '.join(extras)}"

    if preset_key == "fs1":
        trigger = "ps1 style"
        extras = ["game screenshot", "computer generated image", "low poly", "pixelated", "retro 3d", "ps1 graphics", "low resolution render", "n64 style"]
        if subject == "character":
            extras.extend(["blocky character model", "limited texture detail"])
        elif subject == "scene":
            extras.extend(["early 3d environment", "foggy draw distance"])
        elif subject == "object":
            extras.extend(["low poly model", "flat textures"])
        prefix = f"({trigger})" if trigger.lower() not in text.lower() else ""
        body = f"{text}, {', '.join(extras)}"
        return f"{prefix}, {body}" if prefix else body

    if preset_key == "lo_fi":
        trigger = "dreamyvibes artstyle"
        prefix = trigger if trigger.lower() not in text.lower() else ""
        extras = ["dreamy", "soft pastel colors", "atmospheric", "cozy mood", "painterly", "lo-fi aesthetic"]
        if subject == "scene":
            extras.extend(["ambient light", "quiet atmosphere", "depth of field"])
        elif subject == "character":
            extras.extend(["gentle expression", "soft focus", "warm tones"])
        elif subject == "object":
            extras.extend(["still life", "soft shadows", "intimate scale"])
        extras.extend(scene_extras)
        body = f"{text}, {', '.join(extras)}"
        return f"{prefix}, {body}" if prefix else body

    extras: list[str] = []
    if image_style == "realistic":
        extras.extend([
            "photorealistic",
            "detailed skin and textures",
            "natural cinematic lighting",
            "35mm photography look",
            "sharp focus",
        ])
    else:
        extras.extend([
            "highly detailed",
            "clean composition",
            "dynamic lighting",
            "crisp edges and textures",
        ])
    if has_references:
        extras.append("preserve key subjects and composition from reference images")
    if selected_loras:
        extras.append("respect selected LoRA style")
    extras.extend(scene_extras)
    return f"{text}, {', '.join(extras)}"


def register_message_routes(bp: Blueprint, ctx: AppContext) -> None:
    @bp.route("/api/conversations/<conversation_id>/messages", methods=["POST"])
    def add_message(conversation_id: str) -> tuple[dict, int]:
        profile = ctx.require_profile()
        store = ctx.conversation_store_for(profile)
        convo = store.get(conversation_id)
        if convo is None:
            abort(404, description="Conversation not found")

        requested_mode = ""
        raw_content = ""
        request_id = ""
        attachments: list[dict[str, Any]] = []
        upload_errors: list[str] = []
        reply_to_data: dict | None = None
        incoming_image_style: str | None = None
        incoming_selected_loras: list[str] | None = None

        requested_make_type = ""
        extends_request_id = ""
        content_type = str(request.content_type or "").strip().lower()
        if content_type.startswith("multipart/form-data"):
            raw_content = str(request.form.get("content", "")).strip()
            requested_mode = str(request.form.get("mode", "")).strip().lower()
            requested_make_type = str(request.form.get("make_type", "")).strip().lower()
            extends_request_id = str(request.form.get("extends_request_id", "")).strip()
            request_id = str(request.form.get("request_id", "")).strip()
            attachments, upload_errors = ctx.save_uploaded_images(profile, conversation_id)
            if "image_style" in request.form:
                incoming_image_style = str(request.form.get("image_style", "")).strip().lower()
            if "selected_loras" in request.form:
                incoming_selected_loras = _parse_selected_loras_value(request.form.get("selected_loras", ""))
        else:
            payload = request.get_json(silent=True) or {}
            raw_content = str(payload.get("content", "")).strip()
            requested_mode = str(payload.get("mode", "")).strip().lower()
            requested_make_type = str(payload.get("make_type", "")).strip().lower()
            extends_request_id = str(payload.get("extends_request_id", "")).strip()
            request_id = str(payload.get("request_id", "")).strip()
            if "image_style" in payload:
                incoming_image_style = str(payload.get("image_style", "")).strip().lower()
            if "selected_loras" in payload:
                incoming_selected_loras = _parse_selected_loras_value(payload.get("selected_loras"))
            _rt = payload.get("reply_to")
            if isinstance(_rt, dict) and str(_rt.get("id", "")).strip():
                reply_to_data = {
                    "id": str(_rt.get("id", "")).strip(),
                    "role": str(_rt.get("role", "")).strip(),
                    "excerpt": str(_rt.get("excerpt", ""))[:300].strip(),
                }

        if not raw_content and not attachments:
            return {"error": "Message content or image attachment is required"}, 400

        if incoming_image_style is not None or incoming_selected_loras is not None:
            updated = store.set_image_preferences(
                conversation_id,
                image_style=incoming_image_style,
                selected_loras=incoming_selected_loras,
            )
            if updated is not None:
                convo = updated

        talk_text = _extract_talk_text(raw_content)
        is_forage_request = requested_mode == "forage"
        is_make_request = requested_mode == "make"

        is_make_lane_request = is_make_request and not raw_content.startswith("/")
        is_talk_request = (
            requested_mode == "talk"
            or talk_text is not None
            or (not is_forage_request and not is_make_request and not raw_content.startswith("/"))
        )
        if is_make_lane_request and not raw_content and attachments:
            return {"error": "Describe what to build."}, 400
        if not is_make_lane_request:
            extends_request_id = ""
        normalized_talk = (talk_text if talk_text is not None else raw_content).strip()
        if is_talk_request and not normalized_talk and attachments:
            normalized_talk = "Please analyze the attached file(s)."
        stored_user_content = normalized_talk if is_talk_request else raw_content
        if not stored_user_content and attachments:
            n_docs = sum(1 for a in attachments if str(a.get("type", "")) == "document")
            n_imgs = sum(1 for a in attachments if str(a.get("type", "")) == "image")
            parts = []
            if n_imgs:
                parts.append(f"{n_imgs} image(s)")
            if n_docs:
                parts.append(f"{n_docs} document(s)")
            stored_user_content = f"Uploaded {', '.join(parts)}."
        user_mode = "talk" if is_talk_request else "command"
        request_id = ctx.job_manager.start(
            profile=profile,
            conversation_id=conversation_id,
            request_id=request_id,
            mode=user_mode,
            user_text=stored_user_content,
        )
        if is_make_lane_request and not requested_make_type and raw_content and not raw_content.startswith("/"):
            reply_text = "I would love to do that for you, but you forgot to pick a mode!"
            store.add_message(conversation_id, "assistant", reply_text, mode=user_mode, request_id=request_id)
            ctx.job_manager.finish(
                profile,
                request_id,
                status="completed",
                detail="No-type make guard returned canonical reply.",
            )
            return jsonify({"reply": reply_text, "request_id": request_id}), 200

        convo_project = _normalize_project_slug(convo.get("project"))
        if not str(convo.get("project", "")).strip():
            store.set_project(conversation_id, convo_project)
        project_update = None
        pipeline_store = ctx.pipeline_for(profile)
        project_mode = pipeline_store.get(convo_project)
        request_project_mode = dict(project_mode)
        if is_make_lane_request:
            request_project_mode["mode"] = "make"
            if requested_make_type:
                request_project_mode["target"] = requested_make_type
            if extends_request_id:
                request_project_mode["extends_request_id"] = extends_request_id
        convo_topic_id = str(convo.get("topic_id", "")).strip()
        if convo_topic_id and convo_topic_id != "general":
            try:
                topic_row = ctx.get_topic_engine().get_topic(convo_topic_id)
            except Exception:
                topic_row = None
            resolved_conversation_topic_type = (
                str(topic_row.get("type", "")).strip().lower()
                if isinstance(topic_row, dict)
                else ""
            )
            if resolved_conversation_topic_type:
                request_project_mode["topic_type"] = resolved_conversation_topic_type
                if str(project_mode.get("topic_type", "")).strip().lower() != resolved_conversation_topic_type:
                    try:
                        pipeline_store.set(
                            convo_project,
                            topic_type=resolved_conversation_topic_type,
                        )
                    except Exception:
                        pass
        resolved_topic_type = (
            str(request_project_mode.get("topic_type", "general")).strip().lower() or "general"
        )

        guard = check_content(raw_content)
        if guard.blocked:
            reply_text = guard.reason
            store.add_message(conversation_id, "assistant", reply_text, mode=user_mode, request_id=request_id)
            ctx.job_manager.finish(
                profile,
                request_id,
                status="completed",
                detail="Content guard blocked the message.",
            )
            return jsonify({"reply": reply_text, "request_id": request_id}), 200

        orch = ctx.new_orch(profile)
        if orch.project_slug != convo_project:
            orch.set_project(convo_project)

        lane_guess = ""
        is_foraging_request = False
        is_building_request = False
        effective_make_type = (
            requested_make_type or str(request_project_mode.get("target", "auto")).strip().lower() or "auto"
        )
        if is_forage_request:
            lane_guess = "research"
            is_foraging_request = True
        elif is_make_lane_request:
            # Use make_type from UI picker first, then fall back to project target
            lane_guess = f"build:{effective_make_type or 'auto'}"
            is_building_request = True
        seed_artifact_text = ""
        if is_make_lane_request and extends_request_id:
            seed_artifact_text = _seed_artifact_text_for_extension(orch, convo_project, extends_request_id)

        user_msg = store.add_message(
            conversation_id,
            "user",
            stored_user_content,
            mode=user_mode,
            attachments=attachments,
            foraging=is_foraging_request,
            building=is_building_request if is_building_request else None,
            request_id=request_id,
            reply_to=reply_to_data,
        )
        if user_msg is None:
            abort(404, description="Conversation not found")

        doc_attachments_for_library = [
            dict(row)
            for row in attachments
            if str(row.get("type", "")).strip().lower() == "document" and str(row.get("filename", "")).strip()
        ]
        if doc_attachments_for_library:
            repo_root = ctx.repo_root_for_profile(profile)
            conversation_topic_id = str(convo.get("topic_id", "")).strip()
            conversation_project_slug = _normalize_project_slug(convo.get("project"))

            def _enqueue_library_intake() -> None:
                try:
                    service = ctx.library_service_for(profile)
                    attach_dir = ctx.attachment_dir_for(profile, conversation_id)
                    for row in doc_attachments_for_library:
                        source_file = attach_dir / str(row.get("filename", "")).strip()
                        if not source_file.exists():
                            continue
                        item = service.intake_file(
                            source_file,
                            source_name=str(row.get("name", "")).strip() or source_file.name,
                            mime=str(row.get("mime", "")).strip().lower(),
                            source_kind="general",
                            title="",
                            topic_id=conversation_topic_id if conversation_topic_id not in {"", "general"} else "",
                            project_slug=conversation_project_slug if conversation_project_slug != "general" else "",
                            source_origin="chat_upload",
                            conversation_id=conversation_id,
                        )
                        service.enqueue_ingest(str(item.get("id", "")).strip())
                except Exception:
                    LOGGER.exception("Library auto-intake failed for conversation %s in %s.", conversation_id, repo_root)

            threading.Thread(
                target=_enqueue_library_intake,
                daemon=True,
                name=f"oathweaver-library-chat-{conversation_id[:8]}",
            ).start()

        def _cancel_requested() -> bool:
            return ctx.job_manager.is_cancel_requested(profile, request_id)

        _AGENT_EVENT_STAGES = frozenset({
            "research_pool_started", "research_agent_started", "research_agent_completed",
            "build_pool_started", "build_agent_started", "build_agent_completed",
            "build_quality_gate_passed", "build_quality_gate_failed",
        })

        def _agent_detail_str(stage: str, d: dict) -> str:
            agent = str(d.get("agent", "")).strip()
            if stage == "build_agent_started":
                model = str(d.get("model", "")).strip()
                return f"Agent '{agent}' starting" + (f" ({model})" if model else "")
            if stage == "build_agent_completed":
                return f"Agent '{agent}' done"
            if stage == "build_pool_started":
                total = d.get("agents_total", "")
                make_type = str(d.get("make_type", "")).strip()
                return f"Deploying {total} agents" + (f" — {make_type}" if make_type else "")
            if stage == "research_agent_started":
                directive = str(d.get("directive", "")).strip()[:80]
                return f"Agent '{agent}' on it" + (f" — {directive}" if directive else "")
            if stage == "research_agent_completed":
                finding = str(d.get("finding_preview", "")).strip()[:80]
                return f"Agent '{agent}' done" + (f" — {finding}" if finding else "")
            if stage == "research_pool_started":
                total = d.get("agents_total", "")
                profile = str(d.get("analysis_profile", "")).strip().replace("_", " ")
                return f"Deploying {total} agents" + (f" — {profile}" if profile else "")
            if stage == "build_quality_gate_passed":
                return "Quality gate passed"
            if stage == "build_quality_gate_failed":
                return "Quality gate failed — retrying"
            return str(d.get("note", "")).strip()

        def _pool_progress(stage: str, detail: object = None) -> None:
            if isinstance(detail, dict):
                detail_str = _agent_detail_str(stage, detail) if stage in _AGENT_EVENT_STAGES else str(detail.get("note", "") or "")
                _progress(
                    stage,
                    detail_str,
                    summary_path=str(detail.get("summary_path", "")).strip(),
                    raw_path=str(detail.get("raw_path", "")).strip(),
                    web_stack=(detail if stage == "web_stack_ready" else None),
                    agent_event=(dict(detail, stage=stage) if stage in _AGENT_EVENT_STAGES else None),
                    live_source=(detail if stage == "web_source_discovered" else None),
                )
            else:
                _progress(stage, str(detail or ""))

        def _progress(stage: str, detail: str = "", *, summary_path: str = "", raw_path: str = "", web_stack: dict | None = None, agent_event: dict | None = None, live_source: dict | None = None) -> None:
            ctx.job_manager.update(
                profile,
                request_id,
                stage=stage,
                detail=detail,
                summary_path=summary_path,
                raw_path=raw_path,
                web_stack=web_stack,
                agent_event=agent_event,
            )
            if live_source and isinstance(live_source, dict):
                try:
                    ctx.job_manager.append_live_source(profile, request_id, live_source)
                except Exception:
                    pass

        def _cancel_reply() -> str:
            row = ctx.job_manager.get(profile, request_id) or {}
            summary = ctx.job_manager.progress_text(row)
            return (
                "Request cancelled.\n"
                "I stopped this active job at the next safe checkpoint.\n\n"
                "Where I left off:\n"
                f"{summary}"
            )

        _progress("message_received", "Message accepted by API and queued for processing.")
        _progress("orchestrator_ready", f"Active project: {convo_project}")
        if is_foraging_request:
            ctx.foraging_manager.register_job(
                profile=profile,
                conversation_id=conversation_id,
                request_id=request_id,
                project=convo_project,
                lane=lane_guess or "project",
                topic_type=resolved_topic_type,
                job_key=ctx.job_manager.key(profile, request_id),
            )
            _progress("foraging_started", f"Foraging task started on lane '{lane_guess or 'project'}'.")
        elif ctx.foraging_manager.active_count() > 0:
            ctx.foraging_manager.request_yield(seconds=150.0)
            _progress("foraging_yield_requested", "Foreground chat/cmd requested temporary Foraging yield.")

        if is_building_request:
            ctx.building_manager.register_job(
                profile=profile,
                conversation_id=conversation_id,
                request_id=request_id,
                project=convo_project,
                make_type=effective_make_type,
                lane=lane_guess or "make_longform",
                topic_type=resolved_topic_type,
                extends_request_id=extends_request_id,
                job_key=ctx.job_manager.key(profile, request_id),
            )
            _progress("building_started", f"Build task started — type '{effective_make_type}', lane '{lane_guess or 'make_longform'}'.")

        image_context = ""
        doc_context = ""
        image_analysis_failures: list[str] = []
        pipeline_error = ""
        talk_details: dict[str, Any] = {}
        try:
            image_attachments = [a for a in attachments if str(a.get("type", "")) == "image"]
            doc_attachments = [a for a in attachments if str(a.get("type", "")) == "document"]

            if image_attachments:
                _progress("attachment_analysis", f"Analyzing {len(image_attachments)} image attachment(s).")
                image_context, image_analysis_failures = ctx.describe_image_attachments(
                    profile=profile,
                    conversation_id=conversation_id,
                    orch=orch,
                    attachments=image_attachments,
                    user_text=normalized_talk if is_talk_request else raw_content,
                )
                if image_context.strip():
                    _progress("attachment_analysis_done", "Image context extracted for prompt assembly.")
                elif image_analysis_failures:
                    _progress("attachment_analysis_done", "Image analysis attempted with failures logged.")

            if doc_attachments:
                _progress("attachment_analysis", f"Extracting text from {len(doc_attachments)} document(s).")
                doc_parts: list[str] = []
                for doc_att in doc_attachments:
                    text = str(doc_att.get("extracted_text", "")).strip()
                    name = str(doc_att.get("name", "document"))
                    warning = str(doc_att.get("extraction_warning", "")).strip()
                    if text:
                        doc_parts.append(f"[Document: {name}]\n{text}")
                    elif warning:
                        doc_parts.append(f"[Document: {name} — {warning}]")
                    else:
                        doc_parts.append(f"[Document: {name} — text could not be extracted]")
                doc_context = "\n\n".join(doc_parts)
                if doc_context:
                    _progress("attachment_analysis_done", "Document text extracted for prompt assembly.")

            if _cancel_requested():
                reply_text = _cancel_reply()
                _progress("cancel_acknowledged", "Cancel request accepted before model execution.")
            else:
                reply_text = ""

            if not reply_text and is_talk_request:
                _progress("talk_mode", "Running conversation-layer reply.")
                talk_input = normalized_talk
                if image_context:
                    talk_input = f"{talk_input}\n\n{image_context}".strip()
                if doc_context:
                    talk_input = f"{talk_input}\n\n{doc_context}".strip()
                if not talk_input:
                    reply_text = "Talk mode message is empty. Send text to continue the conversation."
                else:
                    history = _build_talk_history(convo.get("messages", []), limit_turns=16)
                    capture_history = _build_fact_history(convo.get("messages", []), limit_turns=260)
                    reply_text = orch.conversation_reply(
                        talk_input,
                        history=history,
                        capture_history=capture_history,
                        project=convo_project,
                        cancel_checker=_cancel_requested,
                        details_sink=talk_details,
                        progress_callback=_pool_progress,
                    )
                    if _cancel_requested():
                        reply_text = _cancel_reply()
                        _progress("cancel_acknowledged", "Cancel request accepted during conversation reply.")
                _progress("talk_mode_done", "Conversation-layer reply generated.")
            elif not reply_text and raw_content.startswith("/"):
                _progress("command_mode", f"Executing slash command: {raw_content.split(' ', 1)[0]}")
                command_history = _build_command_history(convo.get("messages", []), limit_turns=200)
                fact_history = _build_fact_history(convo.get("messages", []), limit_turns=220)
                history_for_command = fact_history if raw_content.strip().lower() == "/project-facts-refresh" else command_history
                if raw_content.strip().lower() == "/recap":
                    convs = store.list()[:5]
                    lines = ["## Recent Conversations\n"]
                    for row in convs:
                        preview = row.get("summary", "")[:160] or "(no summary yet)"
                        lines.append(f"**{row['title']}** — {row['updated_at'][:10]}\n{preview}\n")
                    reply_text = "\n".join(lines)
                else:
                    reply_text = handle_command(
                        orch,
                        raw_content,
                        command_history=history_for_command,
                        project_mode=project_mode,
                    )
                if raw_content.startswith("/project "):
                    requested = raw_content[len("/project "):].strip()
                    project_update = _normalize_project_slug(requested)
                _progress("command_mode_done", "Slash command execution completed.")
            elif not reply_text:
                _progress("foraging_run", "Running Foraging orchestration.")
                command_input = raw_content if raw_content else "Please analyze the attached file(s)."
                if image_context:
                    command_input = f"{command_input}\n\n{image_context}".strip()
                if doc_context:
                    command_input = f"{command_input}\n\n{doc_context}".strip()
                history = _build_command_history(convo.get("messages", []), limit_turns=18)
                if not orch.project_memory.get_facts(convo_project):
                    orch.refresh_project_facts(history=history, reset=False)
                conversation_summary = store.get_summary(conversation_id) if conversation_id else ""
                reply_text = orch.handle_message(
                    command_input,
                    history=history,
                    project_mode=request_project_mode,
                    cancel_checker=_cancel_requested,
                    pause_checker=ctx.foraging_manager.is_paused,
                    yield_checker=ctx.foraging_manager.should_yield,
                    conversation_summary=conversation_summary,
                    seed_artifact_text=seed_artifact_text,
                    force_research=is_forage_request,
                    force_make=is_make_lane_request,
                    thread_id=conversation_id,
                    details_sink=talk_details,
                    progress_callback=_pool_progress,
                )
                _progress("foraging_run_done", "Foraging orchestrator returned final reply.")
        except Exception as exc:
            pipeline_error = str(exc).strip() or "unknown pipeline error"
            _progress("pipeline_error", pipeline_error)
            row = ctx.job_manager.get(profile, request_id) or {}
            progress_summary = ctx.job_manager.progress_text(row)
            if is_foraging_request:
                reply_text = (
                    "Foraging encountered a non-blocking pipeline error after partial progress.\n"
                    "I preserved checkpoints and output paths so you can continue without losing work.\n\n"
                    "Where I left off:\n"
                    f"{progress_summary}\n\n"
                    f"Internal error: {pipeline_error}"
                )
            else:
                reply_text = (
                    "I hit an internal pipeline error while processing this request.\n\n"
                    "Captured progress:\n"
                    f"{progress_summary}\n\n"
                    f"Internal error: {pipeline_error}"
                )
        finally:
            if is_foraging_request:
                ctx.foraging_manager.unregister_job(ctx.job_manager.key(profile, request_id))
            if is_building_request:
                ctx.building_manager.unregister_job(ctx.job_manager.key(profile, request_id))

        attachment_notes: list[str] = []
        if _cancel_requested() and not str(reply_text or "").strip().lower().startswith("request cancelled"):
            reply_text = _cancel_reply()
            _progress("cancel_acknowledged", "Cancel request accepted before response persistence.")
        if upload_errors:
            attachment_notes.extend(upload_errors)
        if image_analysis_failures:
            attachment_notes.extend([f"Vision note: {item}" for item in image_analysis_failures[:6]])
        if attachment_notes:
            notes_block = "\n".join([f"- {item}" for item in attachment_notes])
            reply_text = f"{reply_text}\n\nAttachment notes:\n{notes_block}"

        reply_text = _strip_trailing_assistant_rule(reply_text)

        if project_update:
            store.set_project(conversation_id, project=project_update)
        ctx.cache_clear(str(profile.get("id", "")))

        job_row = ctx.job_manager.get(profile, request_id) or {}
        web_stack = job_row.get("web_stack") if isinstance(job_row.get("web_stack"), dict) else {}
        msg_meta = _build_message_web_meta(
            web_stack=web_stack,
            web_details=talk_details.get("web_details"),
            research_reply=talk_details.get("research_reply"),
        )
        assistant_msg = store.add_message(
            conversation_id,
            "assistant",
            reply_text,
            mode=("talk" if is_talk_request else "command"),
            foraging=is_foraging_request,
            request_id=request_id,
            meta=msg_meta,
        )
        if assistant_msg is None:
            ctx.job_manager.finish(profile, request_id, status="failed", detail="Failed to persist assistant reply.")
            abort(500, description="Failed to persist assistant reply")

        if is_foraging_request and not pipeline_error:
            try:
                from infra.persistence.repositories import ForageCardRepository as _FCR
                import uuid as _uuid

                card_repo = _FCR(ctx.root)
                job_row = ctx.job_manager.get(profile, request_id) or {}
                summary_path = str(job_row.get("summary_path", "") or "").strip()
                raw_path = str(job_row.get("raw_path", "") or "").strip()
                if summary_path:
                    preview = ""
                    for line in reply_text.strip().splitlines():
                        line = line.strip()
                        if line:
                            preview = line[:300]
                            break
                    card_repo.save_card(
                        {
                            "id": f"fc_{request_id[:12]}_{_uuid.uuid4().hex[:4]}",
                            "title": raw_content[:120] if raw_content else "Forage Research",
                            "project": convo_project or "general",
                            "summary_path": summary_path,
                            "raw_path": raw_path,
                            "query": raw_content[:300] if raw_content else "",
                            "preview": preview,
                            "source_count": 0,
                            "is_pinned": 0,
                            "is_read": 0,
                            "created_at": datetime.now(timezone.utc).isoformat(),
                        }
                    )
            except Exception:
                pass

        updated_early = store.get(conversation_id)
        if updated_early:
            msg_count = len(updated_early.get("messages", []))
            root = ctx.root
            if msg_count >= 4 and msg_count % 4 == 0:
                threading.Thread(target=bg_summarize, args=(conversation_id, store, root), daemon=True).start()
            if msg_count == 4:
                project_slug = str(updated_early.get("project", "")).strip().lower()
                title_is_manual = bool(updated_early.get("title_manually_set", False))
                first_user = next(
                    (
                        str(m.get("content", "")).strip()
                        for m in (updated_early.get("messages", []) or [])
                        if str(m.get("role", "")).strip().lower() == "user"
                        and str(m.get("content", "")).strip()
                        and not str(m.get("content", "")).strip().startswith("/")
                    ),
                    "",
                )
                if project_slug == "general" and not title_is_manual and first_user:
                    threading.Thread(target=bg_retitle, args=(conversation_id, store, root), daemon=True).start()

        updated = store.get(conversation_id)
        if updated is None:
            ctx.job_manager.finish(profile, request_id, status="failed", detail="Failed to load updated conversation.")
            abort(500, description="Failed to load updated conversation")

        if bool(updated.get("has_unread", False)):
            push_payload, push_event_key = ctx.conversation_notification_payload(
                profile=profile,
                conversation=updated,
                message=assistant_msg,
            )
            ctx.dispatch_web_push(str(profile.get("id", "")).strip(), push_payload, event_key=push_event_key)

        if _cancel_requested():
            job_status = "canceled"
            job_detail = "Message pipeline cancelled by user."
        elif pipeline_error:
            job_status = "completed_with_warnings"
            job_detail = "Message pipeline completed with non-blocking recovery after internal error."
        else:
            job_status = "completed"
            job_detail = "Message pipeline completed."
        ctx.job_manager.finish(profile, request_id, status=job_status, detail=job_detail)
        final_job_row = ctx.job_manager.get(profile, request_id) or {}
        if is_foraging_request:
            try:
                ctx.foraging_manager.record_completion(
                    profile=profile,
                    conversation_id=conversation_id,
                    request_id=request_id,
                    project=convo_project,
                    lane=lane_guess or "project",
                    topic_type=resolved_topic_type,
                    job_row=final_job_row,
                    status=job_status,
                )
            except Exception:
                LOGGER.exception("Failed to record foraging completion for %s.", request_id)
        if is_building_request:
            try:
                ctx.building_manager.record_completion(
                    profile=profile,
                    conversation_id=conversation_id,
                    request_id=request_id,
                    project=convo_project,
                    make_type=effective_make_type,
                    lane=lane_guess or "make_longform",
                    topic_type=resolved_topic_type,
                    job_row=final_job_row,
                    status=job_status,
                )
            except Exception:
                LOGGER.exception("Failed to record building completion for %s.", request_id)

        return {"conversation": updated, "assistant_message": assistant_msg, "request_id": request_id}, 200

    @bp.route("/api/conversations/<conversation_id>/image-tool/generate", methods=["POST"])
    def image_tool_generate(conversation_id: str) -> tuple[dict, int]:
        return {"ok": False, "error": "Image generation is disabled in this repository."}, 410

    @bp.route("/api/conversations/<conversation_id>/image-tool/video-generate", methods=["POST"])
    def image_tool_video_generate(conversation_id: str) -> tuple[dict, int]:
        return {"ok": False, "error": "Video generation is disabled in this repository."}, 410

    @bp.route("/api/conversations/<conversation_id>/image-tool/bg-enhance", methods=["POST"])
    def image_tool_bg_enhance(conversation_id: str) -> tuple[dict, int]:
        return {"ok": False, "error": "Image enhancement is disabled in this repository."}, 410
