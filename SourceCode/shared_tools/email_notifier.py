from __future__ import annotations

import json
import smtplib
from email.mime.text import MIMEText
from pathlib import Path
from typing import Any

from shared_tools.secret_files import ensure_secret_mode, write_secret_text

_CONFIG_REL = Path("Runtime") / "config" / "email_config.json"

_DEFAULTS: dict[str, Any] = {
    "smtp_host": "smtp.gmail.com",
    "smtp_port": 587,
    "notification_email": "",
    "smtp_user": "",
    "smtp_password": "",
    "dnd_enabled": False,
    "dnd_start": "22:00",
    "dnd_end": "08:00",
}


def load_email_config(root: Path) -> dict[str, Any]:
    path = root / _CONFIG_REL
    if not path.exists():
        return dict(_DEFAULTS)
    try:
        ensure_secret_mode(path)
        data = json.loads(path.read_text(encoding="utf-8"))
        return {**_DEFAULTS, **data} if isinstance(data, dict) else dict(_DEFAULTS)
    except Exception:
        return dict(_DEFAULTS)


def save_email_config(root: Path, config: dict[str, Any]) -> None:
    path = root / _CONFIG_REL
    path.parent.mkdir(parents=True, exist_ok=True)
    clean: dict[str, Any] = {
        "smtp_host": str(config.get("smtp_host", "smtp.gmail.com")).strip() or "smtp.gmail.com",
        "smtp_port": int(config.get("smtp_port", 587)),
        "notification_email": str(config.get("notification_email", "")).strip(),
        "smtp_user": str(config.get("smtp_user", "")).strip(),
        "smtp_password": str(config.get("smtp_password", "")).strip(),
        "dnd_enabled": bool(config.get("dnd_enabled", False)),
        "dnd_start": str(config.get("dnd_start", "22:00")).strip() or "22:00",
        "dnd_end": str(config.get("dnd_end", "08:00")).strip() or "08:00",
    }
    write_secret_text(path, json.dumps(clean, indent=2, ensure_ascii=True))


def is_configured(config: dict[str, Any]) -> bool:
    return bool(
        config.get("notification_email")
        and config.get("smtp_user")
        and config.get("smtp_password")
    )


def is_dnd_active(config: dict[str, Any]) -> bool:
    if not config.get("dnd_enabled"):
        return False
    try:
        from datetime import datetime as _dt
        now = _dt.now()
        now_t = now.hour * 60 + now.minute

        def _to_minutes(s: str) -> int:
            h, m = str(s).split(":")
            return int(h) * 60 + int(m)

        start_t = _to_minutes(str(config.get("dnd_start", "22:00")))
        end_t = _to_minutes(str(config.get("dnd_end", "08:00")))
        if start_t <= end_t:
            return start_t <= now_t < end_t
        return now_t >= start_t or now_t < end_t
    except Exception:
        return False


def _minutes_to_time_str(minutes: int) -> str:
    """Convert an integer minute count to a human-readable 'Xh Ym' string."""
    if minutes <= 0:
        return "now"
    if minutes < 60:
        return f"{minutes} min"
    h = minutes // 60
    m = minutes % 60
    if m == 0:
        return "1 hr" if h == 1 else f"{h} hrs"
    return f"{h}h {m}m"


def format_subject(member_names: list[str], title: str, offset_minutes: int, *,
                   minutes_remaining: int | None = None) -> str:
    time_str = _minutes_to_time_str(minutes_remaining if minutes_remaining is not None else offset_minutes)
    name_part = ", ".join(n for n in member_names if n).strip()
    return f"{name_part}-{title}: Starts in {time_str}" if name_part else f"{title}: Starts in {time_str}"


def format_body(event: dict[str, Any], offset_minutes: int) -> str:
    lines = [
        f"Event:    {event.get('title', '')}",
        f"Date:     {event.get('date', '')}",
        f"Time:     {event.get('start_time', '')}",
    ]
    end = str(event.get("end_time", "")).strip()
    if end:
        lines.append(f"End:      {end}")
    location = str(event.get("location", "")).strip()
    if location:
        lines.append(f"Location: {location}")
    names = [n for n in event.get("member_names", []) if str(n or "").strip()]
    if names:
        lines.append(f"Going:    {', '.join(names)}")
    notes = str(event.get("notes", "")).strip()
    if notes:
        lines.append(f"Notes:    {notes}")
    lines.append("")
    lines.append("Oathweaver reminder — automated.")
    return "\n".join(lines)


def format_task_nudge_subject(owner_name: str, items: list[dict[str, Any]]) -> str:
    is_last = any(item.get("is_last_block") for item in items)
    is_morning = all(item.get("is_morning") for item in items)
    if is_last:
        tag = "LAST CHANCE"
    elif is_morning:
        tag = "Morning Reminder"
    else:
        tag = "Nudge"
    if len(items) == 1:
        title = str(items[0]["task"].get("title", "Task")).strip()
        return f"[{owner_name}][{tag}]: {title} due Today!"
    return f"[{owner_name}][{tag}]: {len(items)} tasks due Today!"


def format_task_nudge_body(owner_name: str, items: list[dict[str, Any]]) -> str:
    is_last = any(item.get("is_last_block") for item in items)
    is_morning = all(item.get("is_morning") for item in items)
    block = items[0].get("block", 12) if items else 12

    if is_morning:
        header = f"Good morning, {owner_name}! Here's what's on your plate for today:"
        footer = "Have a productive day. — Oathweaver"
    elif is_last:
        header = (
            f"It's 10 PM, {owner_name}. The following tasks were due today and "
            f"are still open. This is the last reminder — they'll carry over to "
            f"tomorrow if not finished tonight."
        )
        footer = "Sort it out. — Oathweaver"
    else:
        hour_12 = block % 12 or 12
        ampm = "AM" if block < 12 else "PM"
        header = f"Hey {owner_name}, still open as of {hour_12} {ampm}:"
        footer = "Oathweaver task nudge — automated."

    lines = [header, ""]
    for item in items:
        task = item["task"]
        title = str(task.get("title", "Untitled")).strip()
        priority = str(task.get("priority", "medium")).strip()
        rolled = str(task.get("rolled_from_date", "")).strip()
        carry_tag = f"  [carried over from {rolled}]" if rolled else ""
        lines.append(f"  - {title} [{priority} priority]{carry_tag}")
    lines += ["", footer]
    return "\n".join(lines)


def send_notification_email(config: dict[str, Any], subject: str, body: str) -> None:
    msg = MIMEText(body, "plain", "utf-8")
    msg["Subject"] = subject
    msg["From"] = config["smtp_user"]
    msg["To"] = config["notification_email"]
    host = str(config.get("smtp_host", "smtp.gmail.com")).strip() or "smtp.gmail.com"
    port = int(config.get("smtp_port", 587))
    with smtplib.SMTP(host, port, timeout=20) as smtp:
        smtp.ehlo()
        smtp.starttls()
        smtp.login(str(config["smtp_user"]), str(config["smtp_password"]))
        smtp.sendmail(str(config["smtp_user"]), [str(config["notification_email"])], msg.as_string())
