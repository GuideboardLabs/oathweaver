"""daily_digest.py — Assemble a morning digest from local weather and watchtower research cards.

Usage:
    from shared_tools.daily_digest import build_digest
    text = build_digest(repo_root)  # returns a short plain-text summary
"""
from __future__ import annotations

import logging
from datetime import date, datetime, timedelta
from pathlib import Path

LOGGER = logging.getLogger(__name__)

_TODAY_FMT = "%Y-%m-%d"
_DISPLAY_FMT = "%A, %B %-d"


def build_digest(repo_root: Path, user_id: str | None = None) -> str:
    """Build a plain-text morning digest.  Returns an empty string on failure."""
    try:
        return _build(repo_root, user_id)
    except Exception:
        LOGGER.exception("daily_digest: build failed")
        return ""


def _build(repo_root: Path, user_id: str | None) -> str:
    today = date.today()
    tomorrow = today + timedelta(days=1)
    today_str = today.strftime(_TODAY_FMT)
    tomorrow_str = tomorrow.strftime(_TODAY_FMT)
    today_label = today.strftime(_DISPLAY_FMT)

    lines: list[str] = [f"Good morning! Here's your day — {today_label}."]

    # ------------------------------------------------------------------
    # Weather
    # ------------------------------------------------------------------
    try:
        import json as _json
        settings_path = repo_root / "Runtime" / "config" / "oathweaver_settings.json"
        cfg: dict = {}
        if settings_path.exists():
            try:
                raw_cfg = _json.loads(settings_path.read_text(encoding="utf-8"))
                cfg = raw_cfg if isinstance(raw_cfg, dict) else {}
            except Exception:
                pass
        lat = cfg.get("digest_location_lat")
        lon = cfg.get("digest_location_lon")
        label = str(cfg.get("digest_location_label", "") or "").strip()
        if lat is not None and lon is not None:
            from shared_tools.weather_service import get_weather_summary
            wx = get_weather_summary(float(lat), float(lon))
            if wx:
                location_suffix = f" in {label}" if label else ""
                lines[0] += f"\n🌤 {wx}{location_suffix}"
    except Exception:
        pass

    # ------------------------------------------------------------------
    # Watchtower: any new unread research cards from overnight
    # ------------------------------------------------------------------
    try:
        from web_gui.bootstrap import get_watchtower
        wt = get_watchtower(repo_root)
        unread = wt.unread_count()
        if unread:
            lines.append(f"\n{unread} unread research card(s) waiting in Oathweaver.")
    except Exception:
        pass

    return "\n".join(lines)
