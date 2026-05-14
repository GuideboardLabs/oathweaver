from __future__ import annotations

import hmac
import ipaddress
import os
import secrets
import time
import uuid
from pathlib import Path
from typing import Any

from core.kernel_commands import KernelCommandService
from shared_tools.secret_files import ensure_secret_mode, write_secret_text


def _is_loopback_host(host: str) -> bool:
    text = str(host or "").strip().lower()
    if not text:
        return True
    if text in {"localhost", "127.0.0.1", "::1"}:
        return True
    if ":" in text and not text.startswith("[") and text.count(":") == 1:
        text = text.rsplit(":", 1)[0].strip()
    if text.startswith("[") and text.endswith("]"):
        text = text[1:-1]
    try:
        return ipaddress.ip_address(text).is_loopback
    except ValueError:
        return False


def _load_or_create_api_token(path: Path) -> str:
    try:
        if path.exists():
            token = path.read_text(encoding="utf-8").strip()
            if token:
                ensure_secret_mode(path)
                return token
    except OSError:
        pass
    token = secrets.token_urlsafe(48)
    write_secret_text(path, token)
    return token


def create_openai_compatible_app(repo_root: Path, *, bind_host: str | None = None):
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
    resolved_bind_host = str(bind_host or os.getenv("OATHWEAVER_API_HOST", "127.0.0.1")).strip() or "127.0.0.1"
    require_auth = not _is_loopback_host(resolved_bind_host)
    token_path = Path(repo_root) / "Runtime" / "state" / "api_token"
    api_token = _load_or_create_api_token(token_path)

    @app.before_request
    def _auth_gate():  # type: ignore[no-untyped-def]
        if not require_auth:
            return None
        auth_header = str(request.headers.get("Authorization", "")).strip()
        expected = f"Bearer {api_token}"
        if not auth_header or not hmac.compare_digest(auth_header, expected):
            return jsonify({"error": {"message": "Unauthorized"}}), 401
        return None

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
