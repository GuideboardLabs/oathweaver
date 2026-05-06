from __future__ import annotations

import time
import uuid
from pathlib import Path
from typing import Any

from core.kernel_commands import KernelCommandService


def create_openai_compatible_app(repo_root: Path):
    """Create a minimal OpenAI-compatible local API wrapper over kernel commands.

    Flask is imported lazily so this module can be imported in environments
    where web dependencies are not installed.
    """

    try:
        from flask import Flask, jsonify, request
    except Exception as exc:  # pragma: no cover - runtime dependency path
        raise RuntimeError("Flask is required for interfaces.api.server") from exc

    app = Flask(__name__)
    service = KernelCommandService(Path(repo_root))

    @app.get("/v1/models")
    def list_models():
        text = service.orchestrator.local_models_text()
        rows = []
        for line in str(text or "").splitlines():
            name = str(line or "").strip("- ").strip()
            if not name:
                continue
            rows.append({"id": name, "object": "model", "owned_by": "local"})
        return jsonify({"object": "list", "data": rows}), 200

    @app.post("/v1/chat/completions")
    def chat_completions():
        payload = request.get_json(silent=True) or {}
        messages = payload.get("messages", []) if isinstance(payload.get("messages", []), list) else []
        history: list[dict[str, str]] = []
        user_text = ""
        for row in messages:
            if not isinstance(row, dict):
                continue
            role = str(row.get("role", "")).strip().lower()
            content = str(row.get("content", "")).strip()
            if not role or not content:
                continue
            history.append({"role": role, "content": content})
            if role == "user":
                user_text = content
        if not user_text:
            return jsonify({"error": {"message": "messages must include at least one user turn"}}), 400

        result = service.pipeline_run(text=user_text, history=history[:-1])
        reply = str(result.get("reply", "")).strip()
        if not reply:
            reply = ""

        created = int(time.time())
        response_id = f"chatcmpl_{uuid.uuid4().hex[:22]}"
        return (
            jsonify(
                {
                    "id": response_id,
                    "object": "chat.completion",
                    "created": created,
                    "model": str(payload.get("model", "oathweaver-local")),
                    "choices": [
                        {
                            "index": 0,
                            "message": {"role": "assistant", "content": reply},
                            "finish_reason": "stop",
                        }
                    ],
                    "usage": {
                        "prompt_tokens": 0,
                        "completion_tokens": 0,
                        "total_tokens": 0,
                    },
                    "kernel": {
                        "trace_ledger": result.get("trace_ledger", {}),
                        "auditor_report": result.get("auditor_report", {}),
                        "watchtower_scan": result.get("watchtower_scan", {}),
                    },
                }
            ),
            200,
        )

    @app.post("/v1/kernel/watchtower/scan")
    def kernel_watchtower_scan():
        payload = request.get_json(silent=True) or {}
        project = str(payload.get("project", "")).strip()
        return jsonify(service.watchtower_scan(project=project)), 200

    @app.get("/v1/kernel/memory")
    def kernel_memory_inspect():
        project = str(request.args.get("project", "")).strip()
        limit = int(request.args.get("limit", "40") or 40)
        return jsonify(service.memory_inspect(project=project, limit=limit)), 200

    @app.get("/v1/kernel/audit")
    def kernel_audit_report():
        run_id = str(request.args.get("run_id", "")).strip()
        return jsonify(service.audit_report(run_id=run_id)), 200

    @app.get("/v1/kernel/benchmark/backend-export")
    def kernel_benchmark_backend_export():
        project = str(request.args.get("project", "")).strip()
        limit = int(request.args.get("limit", "500") or 500)
        return jsonify(service.benchmark_backend_export(project=project, limit=limit)), 200

    @app.get("/v1/kernel/benchmark/workflow-eval")
    def kernel_benchmark_workflow_eval():
        run_id = str(request.args.get("run_id", "")).strip()
        profile = str(request.args.get("hardware_profile", "8gb_vram_16gb_ram")).strip() or "8gb_vram_16gb_ram"
        return jsonify(service.benchmark_workflow_eval(run_id=run_id, hardware_profile=profile)), 200

    return app
