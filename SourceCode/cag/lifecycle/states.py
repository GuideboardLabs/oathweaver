from __future__ import annotations

from dataclasses import dataclass
from typing import Any


LIFECYCLE_STATES: tuple[str, ...] = (
    "candidate",
    "accepted",
    "superseded",
    "deprecated",
    "expired",
    "benchmark-derived",
    "watchtower-derived",
    "user-confirmed",
)

_HUMAN_STATUSES: tuple[str, ...] = ("unreviewed", "accepted", "rejected")

_STATE_SET = set(LIFECYCLE_STATES)
_HUMAN_SET = set(_HUMAN_STATUSES)

_TRANSITIONS: dict[str, set[str]] = {
    "candidate": {"accepted", "deprecated", "expired", "benchmark-derived", "watchtower-derived", "user-confirmed"},
    "accepted": {"superseded", "deprecated", "expired", "user-confirmed"},
    "benchmark-derived": {"accepted", "superseded", "deprecated", "expired", "user-confirmed"},
    "watchtower-derived": {"accepted", "superseded", "deprecated", "expired", "user-confirmed"},
    "user-confirmed": {"superseded", "deprecated", "expired"},
    "superseded": {"deprecated", "expired"},
    "deprecated": {"expired"},
    "expired": set(),
}


@dataclass(frozen=True)
class LifecycleTransition:
    previous: str
    next: str
    allowed: bool
    reason: str = ""

    def as_dict(self) -> dict[str, Any]:
        return {
            "previous": self.previous,
            "next": self.next,
            "allowed": self.allowed,
            "reason": self.reason,
        }


def normalize_status(value: str, *, default: str = "candidate") -> str:
    key = str(value or "").strip().lower()
    if key in _STATE_SET:
        return key
    return default


def normalize_human_status(value: str, *, default: str = "unreviewed") -> str:
    key = str(value or "").strip().lower()
    if key in _HUMAN_SET:
        return key
    return default


def can_transition(previous: str, next_status: str) -> LifecycleTransition:
    prev = normalize_status(previous)
    nxt = normalize_status(next_status, default=next_status)
    if nxt not in _STATE_SET:
        return LifecycleTransition(previous=prev, next=nxt, allowed=False, reason="unknown_target_state")
    if prev == nxt:
        return LifecycleTransition(previous=prev, next=nxt, allowed=True, reason="no_change")
    allowed_targets = _TRANSITIONS.get(prev, set())
    if nxt in allowed_targets:
        return LifecycleTransition(previous=prev, next=nxt, allowed=True)
    return LifecycleTransition(previous=prev, next=nxt, allowed=False, reason="illegal_transition")


def lifecycle_states() -> list[str]:
    return list(LIFECYCLE_STATES)


def human_statuses() -> list[str]:
    return list(_HUMAN_STATUSES)
