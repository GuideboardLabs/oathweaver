from __future__ import annotations

from pathlib import Path
from typing import Any

from shared_tools.cag_memory_facade import CAGMemoryFacade
from shared_tools.web_research import WebResearchEngine


def forage(repo_root: Path, query: str, depth: str = "quick") -> dict[str, Any]:
    engine = WebResearchEngine(Path(repo_root))
    clean_depth = str(depth or "quick").strip().lower()
    fn = engine.run_quick_query if clean_depth != "full" else engine.run_query
    result = fn(
        project="general",
        lane="research",
        query=str(query or "").strip(),
        reason="mcp_tool",
        note=f"mcp:{clean_depth}",
    )
    return {
        "ok": bool(result.get("ok", False)),
        "query": str(query or ""),
        "depth": clean_depth,
        "source_count": int(result.get("source_count", 0) or 0),
        "summary": str(result.get("message", ""))[:240],
        "source_path": str(result.get("source_path", "")),
        "provider": str(result.get("provider", "")),
        "result": result,
    }


def recall(
    repo_root: Path,
    query: str,
    *,
    kinds: list[str] | None = None,
    project: str = "general",
    conversation_id: str = "",
) -> dict[str, Any]:
    facade = CAGMemoryFacade(Path(repo_root))
    raw_kinds = kinds if isinstance(kinds, list) else ["episodic", "semantic", "procedural"]
    clean_kinds = tuple(
        k
        for k in (str(item or "").strip().lower() for item in raw_kinds)
        if k in {"episodic", "semantic", "procedural"}
    )
    payload = facade.recall(
        str(query or ""),
        kinds=clean_kinds if clean_kinds else ("episodic", "semantic"),
        project=str(project or "general").strip() or "general",
        conversation_id=str(conversation_id or "").strip(),
    )
    return payload


def make_artifact(repo_root: Path, type_id: str, spec: str) -> dict[str, Any]:
    from orchestrator.main import OathweaverOrchestrator

    orch = OathweaverOrchestrator(Path(repo_root))
    mode = {
        "mode": "make",
        "target": str(type_id or "auto").strip().lower() or "auto",
        "topic_type": "general",
    }
    reply = orch.handle_message(
        str(spec or "").strip(),
        history=[],
        project_mode=mode,
        force_make=True,
    )
    return {
        "ok": True,
        "type_id": str(type_id or "").strip().lower(),
        "reply": str(reply or ""),
    }
