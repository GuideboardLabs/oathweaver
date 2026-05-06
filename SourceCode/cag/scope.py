from __future__ import annotations

from dataclasses import dataclass
from typing import Any


SCOPE_LEVELS: tuple[str, ...] = ("domain", "topic", "thread", "project", "run")
_SCOPE_SET = set(SCOPE_LEVELS)


def normalize_scope_level(value: str) -> str:
    key = str(value or "").strip().lower()
    return key if key in _SCOPE_SET else "project"


@dataclass(frozen=True)
class ScopeRow:
    level: str
    domain: str = ""
    topic: str = ""
    thread: str = ""
    project: str = ""
    run: str = ""

    def key(self) -> str:
        parts = [
            f"level={self.level}",
            f"domain={self.domain}",
            f"topic={self.topic}",
            f"thread={self.thread}",
            f"project={self.project}",
            f"run={self.run}",
        ]
        return "|".join(parts)


def build_scope(
    *,
    level: str,
    domain: str = "",
    topic: str = "",
    thread: str = "",
    project: str = "",
    run: str = "",
) -> ScopeRow:
    normalized = normalize_scope_level(level)
    return ScopeRow(
        level=normalized,
        domain=str(domain or "").strip(),
        topic=str(topic or "").strip(),
        thread=str(thread or "").strip(),
        project=str(project or "").strip(),
        run=str(run or "").strip(),
    )


def scope_chain(row: ScopeRow) -> list[ScopeRow]:
    ordered: list[ScopeRow] = []
    levels = list(SCOPE_LEVELS)
    idx = levels.index(normalize_scope_level(row.level))
    for current in levels[: idx + 1]:
        ordered.append(
            ScopeRow(
                level=current,
                domain=row.domain if current in {"domain", "topic", "thread", "project", "run"} else "",
                topic=row.topic if current in {"topic", "thread", "project", "run"} else "",
                thread=row.thread if current in {"thread", "project", "run"} else "",
                project=row.project if current in {"project", "run"} else "",
                run=row.run if current in {"run"} else "",
            )
        )
    return ordered


def scope_to_dict(row: ScopeRow) -> dict[str, Any]:
    return {
        "scope": row.key(),
        "scope_level": row.level,
        "domain": row.domain,
        "topic": row.topic,
        "thread": row.thread,
        "project": row.project,
        "run": row.run,
    }

