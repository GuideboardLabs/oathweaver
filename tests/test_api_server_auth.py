from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from tests.common import ensure_runtime
from interfaces.api import server as api_server
from shared_tools.secret_files import write_secret_text


class _FakeKernelService:
    def __init__(self, _repo_root: Path) -> None:
        self.orchestrator = type("Orchestrator", (), {"local_models_text": lambda _self: "- qwen3:8b\n- deepseek-r1:8b"})()

    def pipeline_run(self, *, text: str, history: list[dict[str, str]] | None = None) -> dict:
        _ = history
        return {
            "reply": f"echo:{text}",
            "trace_ledger": {"run_id": "r1"},
            "auditor_report": {"typed_findings": []},
            "watchtower_scan": {"queued_count": 0},
        }

    def watchtower_scan(self, *, project: str = "") -> dict:
        return {"ok": True, "project": project or "general"}

    def memory_inspect(self, *, project: str = "", limit: int = 40) -> dict:
        return {"ok": True, "project": project or "general", "limit": int(limit), "rows": []}

    def audit_report(self, *, run_id: str = "") -> dict:
        return {"ok": True, "run_id": run_id}

    def benchmark_backend_export(self, *, project: str = "", limit: int = 500) -> dict:
        return {"ok": True, "project": project or "general", "limit": int(limit), "rows": []}

    def benchmark_workflow_eval(self, *, run_id: str = "", hardware_profile: str = "8gb_vram_16gb_ram") -> dict:
        return {"ok": True, "run_id": run_id, "hardware_profile": hardware_profile}


class ApiServerAuthTests(unittest.TestCase):
    def setUp(self) -> None:
        tmp = tempfile.TemporaryDirectory(prefix="api_server_auth_")
        self.addCleanup(tmp.cleanup)
        self.repo_root = Path(tmp.name) / "repo"
        self.repo_root.mkdir(parents=True, exist_ok=True)
        ensure_runtime(self.repo_root)

    def _create_app(self, *, bind_host: str):
        with patch("interfaces.api.server.KernelCommandService", _FakeKernelService):
            return api_server.create_openai_compatible_app(self.repo_root, bind_host=bind_host)

    def _token_path(self) -> Path:
        return self.repo_root / "Runtime" / "state" / "api_token"

    def _token_value(self) -> str:
        return self._token_path().read_text(encoding="utf-8").strip()

    def test_token_created_on_boot_and_mode_is_0600(self) -> None:
        _ = self._create_app(bind_host="127.0.0.1")
        token_path = self._token_path()
        self.assertTrue(token_path.exists())
        self.assertTrue(self._token_value())
        self.assertEqual(token_path.stat().st_mode & 0o777, 0o600)

    def test_loopback_bind_allows_calls_without_bearer_token(self) -> None:
        app = self._create_app(bind_host="127.0.0.1")
        with app.test_client() as client:
            self.assertEqual(client.get("/v1/models").status_code, 200)
            self.assertEqual(
                client.post(
                    "/v1/chat/completions",
                    json={"messages": [{"role": "user", "content": "hello"}]},
                ).status_code,
                200,
            )

    def test_non_loopback_bind_requires_bearer_token(self) -> None:
        app = self._create_app(bind_host="0.0.0.0")
        token = self._token_value()
        with app.test_client() as client:
            self.assertEqual(client.get("/v1/models").status_code, 401)
            self.assertEqual(
                client.get("/v1/models", headers={"Authorization": "Bearer wrong-token"}).status_code,
                401,
            )
            self.assertEqual(
                client.get("/v1/models", headers={"Authorization": f"Bearer {token}"}).status_code,
                200,
            )

    def test_rotated_token_file_is_honored_on_next_request(self) -> None:
        app = self._create_app(bind_host="0.0.0.0")
        old_token = self._token_value()
        new_token = "rotated-token-value"
        write_secret_text(self._token_path(), new_token)

        with app.test_client() as client:
            self.assertEqual(
                client.get("/v1/models", headers={"Authorization": f"Bearer {old_token}"}).status_code,
                401,
            )
            self.assertEqual(
                client.get("/v1/models", headers={"Authorization": f"Bearer {new_token}"}).status_code,
                200,
            )

    def test_v1_handlers_cover_happy_and_auth_fail_paths(self) -> None:
        app = self._create_app(bind_host="0.0.0.0")
        token = self._token_value()
        auth = {"Authorization": f"Bearer {token}"}

        cases = [
            ("GET", "/v1/models", None),
            ("POST", "/v1/chat/completions", {"messages": [{"role": "user", "content": "status"}]}),
            ("POST", "/v1/kernel/watchtower/scan", {"project": "general"}),
            ("GET", "/v1/kernel/memory", None),
            ("GET", "/v1/kernel/audit", None),
            ("GET", "/v1/kernel/benchmark/backend-export", None),
            ("GET", "/v1/kernel/benchmark/workflow-eval", None),
        ]

        with app.test_client() as client:
            for method, path, payload in cases:
                with self.subTest(path=path, auth=False):
                    if method == "GET":
                        response = client.get(path)
                    else:
                        response = client.post(path, json=payload)
                    self.assertEqual(response.status_code, 401)

                with self.subTest(path=path, auth=True):
                    if method == "GET":
                        response = client.get(path, headers=auth)
                    else:
                        response = client.post(path, json=payload, headers=auth)
                    self.assertEqual(response.status_code, 200)


if __name__ == "__main__":
    unittest.main()
