from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from cag.memory_store import CAGMemoryStore
from cag.selector import ScopedSelector


@dataclass(frozen=True)
class AdapterConfig:
    repo_root: Path
    project: str = "general"


class CagBenchMemoryAdapter:
    """Expose Oathweaver CAG Memory Store in cag-bench friendly form."""

    def __init__(
        self,
        config: AdapterConfig,
        *,
        store: CAGMemoryStore | None = None,
        selector: ScopedSelector | None = None,
    ) -> None:
        self.config = config
        self.store = store or CAGMemoryStore(config.repo_root)
        self.selector = selector or ScopedSelector()

    def export_rows(
        self,
        *,
        project: str = "",
        statuses: list[str] | None = None,
        limit: int = 800,
    ) -> list[dict[str, Any]]:
        target = str(project or self.config.project).strip() or self.config.project
        rows = self.store.list_rows(
            project=target,
            statuses=statuses,
            include_expired=True,
            include_superseded=True,
            limit=max(1, int(limit)),
        )
        return [self._to_bench_row(x) for x in rows]

    def import_rows(
        self,
        rows: list[dict[str, Any]],
        *,
        project: str = "",
        scope_level: str = "project",
    ) -> list[dict[str, Any]]:
        target_project = str(project or self.config.project).strip() or self.config.project
        persisted: list[dict[str, Any]] = []
        for row in rows:
            if not isinstance(row, dict):
                continue
            payload = self._to_store_row(row, project=target_project, default_scope_level=scope_level)
            persisted.append(self.store.add_row(payload))
        return persisted

    def retrieve_scoped(
        self,
        *,
        task: dict[str, Any],
        project: str = "",
        k: int = 8,
        max_chars: int | None = None,
        return_scores: bool = False,
    ) -> list[dict[str, Any]] | tuple[list[dict[str, Any]], list[dict[str, Any]]]:
        target_project = str(project or self.config.project).strip() or self.config.project
        rows = self.store.list_rows(
            project=target_project,
            statuses=["accepted", "user-confirmed", "benchmark-derived", "watchtower-derived"],
            include_expired=False,
            include_superseded=False,
            limit=1200,
        )
        return self.selector.retrieve_scoped(
            task=dict(task or {}),
            rows=rows,
            k=max(1, int(k)),
            max_chars=max_chars,
            return_scores=bool(return_scores),
        )

    def as_backend(self, *, project: str = "") -> dict[str, Any]:
        target = str(project or self.config.project).strip() or self.config.project

        def _add_memory(row: dict[str, Any]) -> dict[str, Any]:
            payload = self._to_store_row(row, project=target, default_scope_level="project")
            return self.store.add_row(payload)

        def _list_memory() -> list[dict[str, Any]]:
            return self.export_rows(project=target, limit=1200)

        def _retrieve(task: dict[str, Any], *, k: int = 8, max_chars: int | None = None) -> list[dict[str, Any]]:
            out = self.retrieve_scoped(task=task, project=target, k=k, max_chars=max_chars, return_scores=False)
            return [self._to_bench_row(x) for x in out] if isinstance(out, list) else []

        return {
            "backend_name": "oathweaver_cag_memory_store",
            "project": target,
            "add_memory": _add_memory,
            "list_memory": _list_memory,
            "retrieve_scoped": _retrieve,
        }

    @staticmethod
    def _to_bench_row(row: dict[str, Any]) -> dict[str, Any]:
        tags = [str(x).strip() for x in row.get("tags", []) if str(x).strip()]
        promoted = [str(x).strip() for x in row.get("promoted_terms", []) if str(x).strip()]
        return {
            "memory_id": str(row.get("memory_id", "")).strip(),
            "text": str(row.get("text", "")).strip(),
            "scope": str(row.get("scope", "")).strip(),
            "scope_level": str(row.get("scope_level", "")).strip(),
            "memory_type": str(row.get("type", row.get("memory_type", "decision"))).strip(),
            "status": str(row.get("status", "candidate")).strip(),
            "tags": tags,
            "promoted_terms": promoted,
            "continuity_terms": [{"accepted_terms": promoted}] if promoted else [],
            "project": str(row.get("project", "")).strip(),
            "thread": str(row.get("thread", "")).strip(),
            "domain": str(row.get("domain", "")).strip(),
            "topic": str(row.get("topic", "")).strip(),
            "created_at": str(row.get("created_at", "")).strip(),
            "updated_at": str(row.get("updated_at", "")).strip(),
        }

    @staticmethod
    def _to_store_row(row: dict[str, Any], *, project: str, default_scope_level: str) -> dict[str, Any]:
        text = str(row.get("text", "")).strip()
        memory_type = str(row.get("memory_type", row.get("type", "decision"))).strip().lower() or "decision"
        scope_level = str(row.get("scope_level", default_scope_level)).strip().lower() or default_scope_level
        tags = [str(x).strip().lower() for x in row.get("tags", []) if str(x).strip()]
        promoted = [str(x).strip().lower() for x in row.get("promoted_terms", []) if str(x).strip()]
        continuity_terms = row.get("continuity_terms", []) if isinstance(row.get("continuity_terms", []), list) else []
        for item in continuity_terms:
            if not isinstance(item, dict):
                continue
            for term in item.get("accepted_terms", []) if isinstance(item.get("accepted_terms", []), list) else []:
                token = str(term).strip().lower()
                if token and token not in promoted:
                    promoted.append(token)

        return {
            "memory_id": str(row.get("memory_id", "")).strip(),
            "text": text,
            "scope": str(row.get("scope", "")).strip(),
            "scope_level": scope_level,
            "domain": str(row.get("domain", "")).strip(),
            "topic": str(row.get("topic", "")).strip(),
            "thread": str(row.get("thread", "")).strip(),
            "project": str(row.get("project", "")).strip() or project,
            "run": str(row.get("run", "")).strip(),
            "type": memory_type,
            "status": str(row.get("status", "accepted")).strip().lower() or "accepted",
            "evidence": [dict(x) for x in row.get("evidence", []) if isinstance(x, dict)],
            "confidence": float(row.get("confidence", 0.7) or 0.7),
            "human_status": str(row.get("human_status", "unreviewed")).strip(),
            "tags": tags,
            "promoted_terms": promoted,
            "source": str(row.get("source", "cag_bench_adapter")).strip() or "cag_bench_adapter",
            "validation": {
                "task_metadata": True,
                "has_citation": bool(row.get("has_citation", False)),
                "auditor_approved": bool(row.get("auditor_approved", False)),
                "user_accepted": bool(row.get("user_accepted", False)),
                "tests_passed": bool(row.get("tests_passed", False)),
                "benchmark_backed": True,
            },
        }


def build_cag_bench_adapter(repo_root: Path, *, project: str = "general") -> CagBenchMemoryAdapter:
    return CagBenchMemoryAdapter(AdapterConfig(repo_root=Path(repo_root), project=str(project or "general")))
