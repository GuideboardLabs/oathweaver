from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from shared_tools.phase0 import lane_to_pipeline


@dataclass(slots=True)
class WorkerResult:
    """Normalized worker response shared across orchestrator lanes.

    The current codebase still returns flexible dictionaries from many workers.
    This dataclass provides a stable contract the orchestrator can grow toward
    while remaining easy to hydrate from legacy dict payloads.
    """

    lane: str
    status: str = "ok"
    message: str = ""
    summary_path: str | None = None
    artifact_paths: list[str] = field(default_factory=list)
    payload: dict[str, Any] = field(default_factory=dict)
    canceled: bool = False

    @classmethod
    def from_legacy(cls, lane: str, data: dict[str, Any] | None) -> "WorkerResult":
        row = data if isinstance(data, dict) else {}
        artifact_paths: list[str] = []
        for key in ("path", "summary_path"):
            value = row.get(key)
            if isinstance(value, str) and value.strip() and value not in artifact_paths:
                artifact_paths.append(value)
        extra_paths = row.get("artifact_paths")
        if isinstance(extra_paths, list):
            for value in extra_paths:
                if isinstance(value, str) and value.strip() and value not in artifact_paths:
                    artifact_paths.append(value)
        status = "cancelled" if bool(row.get("canceled")) else str(row.get("status", "ok") or "ok")
        return cls(
            lane=lane,
            status=status,
            message=str(row.get("message", "") or ""),
            summary_path=(str(row.get("summary_path", "") or "").strip() or None),
            artifact_paths=artifact_paths,
            payload=dict(row),
            canceled=bool(row.get("canceled")),
        )

    def as_dict(self) -> dict[str, Any]:
        return {
            "lane": self.lane,
            "pipeline": lane_to_pipeline(self.lane),
            "status": self.status,
            "message": self.message,
            "summary_path": self.summary_path,
            "artifact_paths": list(self.artifact_paths),
            "payload": dict(self.payload),
            "canceled": self.canceled,
        }


@dataclass(slots=True)
class ResearchResult(WorkerResult):
    sources: list[dict[str, Any]] = field(default_factory=list)
    conflict_summary: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class MakeResult(WorkerResult):
    delivery_target: str | None = None


@dataclass(slots=True)
class PersonalResult(WorkerResult):
    reminders_created: int = 0
