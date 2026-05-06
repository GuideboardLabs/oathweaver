from __future__ import annotations

import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / 'SourceCode'
if str(SOURCE) not in sys.path:
    sys.path.insert(0, str(SOURCE))
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def ensure_runtime(repo_root: Path) -> None:
    def _ensure_json(path: Path, default) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        if not path.exists():
            path.write_text(json.dumps(default, indent=2), encoding='utf-8')

    _ensure_json(repo_root / 'Runtime' / 'watchtower' / 'watches.json', [])
    _ensure_json(repo_root / 'Runtime' / 'watchtower' / 'briefing_state.json', {})
    _ensure_json(repo_root / 'Runtime' / 'routines' / 'routines.json', [])
    _ensure_json(repo_root / 'Runtime' / 'topics' / 'topics.json', [])
    _ensure_json(repo_root / 'Runtime' / 'project_catalog.json', [])
    _ensure_json(repo_root / 'Runtime' / 'web' / 'settings.json', {'mode': 'off', 'provider': 'auto'})
    (repo_root / 'Runtime' / 'briefings').mkdir(parents=True, exist_ok=True)
    (repo_root / 'Runtime' / 'conversations').mkdir(parents=True, exist_ok=True)
    os.environ.setdefault('OATHWEAVER_OWNER_PASSWORD', 'test-password')
    os.environ.setdefault('OATHWEAVER_AUTH_ENABLED', '0')
