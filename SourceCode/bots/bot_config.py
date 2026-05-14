from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from shared_tools.secret_files import ensure_secret_mode, write_secret_text

_CONFIG_REL = Path("Runtime") / "config" / "bot_config.json"

_DEFAULTS: dict[str, Any] = {
    "telegram": {
        "enabled": False,
        "bot_token": "",
    },
    "discord": {
        "enabled": False,
        "bot_token": "",
        "persona_name": "",
        "persona_notes": "",
    },
    "slack": {
        "enabled": False,
        "bot_token": "",
        "app_token": "",
        "signing_secret": "",
    },
}


def load_bot_config(repo_root: Path) -> dict[str, Any]:
    path = repo_root / _CONFIG_REL
    if not path.exists():
        return _deep_copy_defaults()
    try:
        ensure_secret_mode(path)
        data = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(data, dict):
            return _deep_copy_defaults()
        result = _deep_copy_defaults()
        for platform in result:
            if isinstance(data.get(platform), dict):
                result[platform].update(data[platform])
        return result
    except Exception:
        return _deep_copy_defaults()


def save_bot_config(repo_root: Path, config: dict[str, Any]) -> None:
    path = repo_root / _CONFIG_REL
    path.parent.mkdir(parents=True, exist_ok=True)
    existing = load_bot_config(repo_root)
    for platform in existing:
        if isinstance(config.get(platform), dict):
            existing[platform].update(config[platform])
    write_secret_text(path, json.dumps(existing, indent=2, ensure_ascii=True))


def _deep_copy_defaults() -> dict[str, Any]:
    return {k: dict(v) for k, v in _DEFAULTS.items()}
