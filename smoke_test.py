#!/usr/bin/env python3
from __future__ import annotations

import importlib
import json
import os
import shutil
import sys
import tempfile
import traceback
from pathlib import Path

PASS = "PASS"
FAIL = "FAIL"


def _print(status: str, message: str) -> None:
    print(f"[{status}] {message}")


def _ignore_filter(_src: str, names: list[str]) -> set[str]:
    ignored: set[str] = set()
    bulky = {
        ".git",
        ".venv",
        "node_modules",
        "__pycache__",
        ".pytest_cache",
        ".mypy_cache",
        ".ruff_cache",
        "Archive",
    }
    for name in names:
        if name in bulky:
            ignored.add(name)
    return ignored


def _ensure_json(path: Path, default) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not path.exists():
        path.write_text(json.dumps(default, indent=2), encoding="utf-8")


def _prepare_runtime(repo_root: Path) -> None:
    _ensure_json(repo_root / "Runtime" / "watchtower" / "watches.json", [])
    _ensure_json(repo_root / "Runtime" / "watchtower" / "briefing_state.json", {})
    _ensure_json(repo_root / "Runtime" / "routines" / "routines.json", [])
    _ensure_json(repo_root / "Runtime" / "topics" / "topics.json", [])
    _ensure_json(repo_root / "Runtime" / "project_catalog.json", [])
    _ensure_json(repo_root / "Runtime" / "web" / "settings.json", {"mode": "off", "provider": "auto"})
    (repo_root / "Runtime" / "briefings").mkdir(parents=True, exist_ok=True)
    (repo_root / "Runtime" / "conversations").mkdir(parents=True, exist_ok=True)


class FakeOrchestrator:
    def web_mode_text(self) -> str:
        return "MODE_MARKER"

    def web_provider_text(self) -> str:
        return "PROVIDER_MARKER"

    def set_web_mode(self, mode: str) -> str:
        return f"SET_MODE:{mode}"

    def set_web_provider(self, provider: str) -> str:
        return f"SET_PROVIDER:{provider}"


def main() -> int:
    source_repo = Path(__file__).resolve().parent
    failures = 0

    with tempfile.TemporaryDirectory(prefix="oathweaver_smoke_") as tmpdir:
        tmp_repo = Path(tmpdir) / "Oathweaver"
        shutil.copytree(source_repo, tmp_repo, ignore=_ignore_filter)
        _prepare_runtime(tmp_repo)

        os.environ.setdefault("OATHWEAVER_OWNER_PASSWORD", "smoke-test-password")
        os.environ.setdefault("OATHWEAVER_AUTH_ENABLED", "0")

        sys.path.insert(0, str(tmp_repo / "SourceCode"))
        sys.path.insert(0, str(tmp_repo))

        try:
            appmod = importlib.import_module("web_gui.app")
            _print(PASS, "Imported web_gui.app")
        except Exception:
            _print(FAIL, "Importing web_gui.app failed")
            traceback.print_exc()
            return 1

        try:
            wt = getattr(appmod, "_watchtower", None)
            rt = getattr(appmod, "_routine_engine", None)
            wt_alive = bool(wt and getattr(wt, "_thread", None) and wt._thread.is_alive())
            rt_alive = bool(rt and getattr(rt, "_thread", None) and rt._thread.is_alive())
            assert not wt_alive and not rt_alive
            _print(PASS, "Background services are not started at import time")
        except Exception:
            failures += 1
            _print(FAIL, "Background services started too early")
            traceback.print_exc()

        try:
            chat_helpers = importlib.import_module("web_gui.chat_helpers")
            handle_command = chat_helpers.handle_command
            fake = FakeOrchestrator()
            provider_text = handle_command(fake, "/web-provider")
            mode_text = handle_command(fake, "/web-mode")
            assert provider_text == "PROVIDER_MARKER"
            assert mode_text == "MODE_MARKER"
            assert handle_command(fake, "/web-provider auto") == "SET_PROVIDER:auto"
            assert handle_command(fake, "/web-mode ask") == "SET_MODE:ask"
            _print(PASS, "Command routing for /web-provider and /web-mode is correct")
        except Exception:
            failures += 1
            _print(FAIL, "Command routing regression detected")
            traceback.print_exc()

        try:
            make_catalog = importlib.import_module("orchestrator.services.make_catalog")
            stack_summary = getattr(make_catalog, "stack_summary")
            summary_text = str(stack_summary() or "")
            assert "tool" in summary_text and "web_app" in summary_text and "desktop_app" in summary_text
            assert "Flask 3.x" in summary_text and "Vue 3.5" in summary_text
            web_app_entry = dict(getattr(make_catalog, "MAKE_CATALOG", {}).get("web_app", {}) or {})
            assert web_app_entry.get("scaffold_path") == "canon/web_app_v1"
            _print(PASS, "Stack summary helper exposes fixed stack capabilities")
        except Exception:
            failures += 1
            _print(FAIL, "Stack summary helper check failed")
            traceback.print_exc()

        try:
            canon_renderer = importlib.import_module("agents_make.canon.renderer")
            copy_scaffold = getattr(canon_renderer, "copy_scaffold")
            list_slots = getattr(canon_renderer, "list_slots")
            verify_plumbing_intact = getattr(canon_renderer, "verify_plumbing_intact")
            probe_dir = tmp_repo / "Runtime" / "smoke_canon_probe"
            copy_scaffold("web_app_v1", probe_dir)
            slots = list_slots(probe_dir)
            app_slots = slots.get(probe_dir / "app.py", [])
            assert "routes-feature" in app_slots and "imports-feature" in app_slots
            assert verify_plumbing_intact(probe_dir, "web_app_v1") == []
            _print(PASS, "Canon scaffold copy, slot discovery, and plumbing checks are healthy")
        except Exception:
            failures += 1
            _print(FAIL, "Canon scaffold sanity check failed")
            traceback.print_exc()

        try:
            research_service = importlib.import_module("orchestrator.services.research_service")
            guard = getattr(research_service, "_is_stack_decided_question")
            assert guard("Should I use SQLite or Postgres?", "general") is True
            assert guard("React vs Vue?", "general") is True
            assert guard("Should I use SQLite or Postgres?", "technical") is False
            _print(PASS, "Research stack-decision guard behavior is correct")
        except Exception:
            failures += 1
            _print(FAIL, "Research stack-decision guard check failed")
            traceback.print_exc()

        try:
            mainmod = importlib.import_module("orchestrator.main")
            host_cls = getattr(mainmod, "OathweaverOrchestrator")
            host = host_cls.__new__(host_cls)
            host.repo_root = tmp_repo
            artifacts = host._format_research_artifacts_block(
                {
                    "summary_path": str(tmp_repo / "Projects" / "demo" / "research_summaries" / "summary with space.md"),
                    "raw_path": str(tmp_repo / "Projects" / "demo" / "research_raw" / "raw.md"),
                }
            )
            assert "](/api/files/read?path=Projects/demo/research_summaries/summary%20with%20space.md)" in artifacts
            assert "](/api/files/read?path=Projects/demo/research_raw/raw.md)" in artifacts
            _print(PASS, "Research artifact block emits clickable markdown file links")
        except Exception:
            failures += 1
            _print(FAIL, "Research artifact link formatting check failed")
            traceback.print_exc()

        try:
            synth = importlib.import_module("agents_research.synthesizer")

            class _FakeClient:
                def chat(self, **_kwargs):
                    return "Revised summary\n---CRITIQUE---\nAudit notes"

            revised, critique = synth.run_skeptic_pass(
                question="q",
                synthesis="Base summary",
                client=_FakeClient(),
                model_cfg={"model": "dummy"},
                findings=[],
            )
            assert revised == "Revised summary"
            assert critique == "Audit notes"
            _print(PASS, "Skeptic pass returns revised summary plus critique sidecar")
        except Exception:
            failures += 1
            _print(FAIL, "Skeptic pass contract check failed")
            traceback.print_exc()

        try:
            readme_text = (tmp_repo / "README.md").read_text(encoding="utf-8")
            assert "Flask 3.x + Vue 3.5" in readme_text
            assert "system-fixed" in readme_text
            assert "Technical topic" in readme_text
            assert "Skeptic sidecar" in readme_text
            assert "Public-content guardrail" in readme_text
            assert "Canon v1" in readme_text
            _print(PASS, "README includes current stack and routing guidance")
        except Exception:
            failures += 1
            _print(FAIL, "README accuracy check failed")
            traceback.print_exc()

        try:
            app = appmod.create_app()
            _print(PASS, "create_app() returned a Flask app")
        except Exception:
            failures += 1
            _print(FAIL, "create_app() failed")
            traceback.print_exc()
            return 1

        endpoints = [
            "/",
            "/api/health",
            "/api/auth/status",
            "/api/projects",
            "/api/topics",
            "/api/routines",
            "/api/watchtower/watches",
            "/api/panel/status",
            "/api/foraging/state",
        ]

        try:
            with app.test_client() as client:
                for endpoint in endpoints:
                    response = client.get(endpoint)
                    assert response.status_code < 500, f"{endpoint} returned {response.status_code}"
                _print(PASS, "Core routes returned non-5xx responses")

                health_resp = client.get("/api/health")
                health_data = health_resp.get_json()
                assert health_data.get("ok") is True, "/api/health missing ok=True"
                assert "checks" in health_data, "/api/health missing checks payload"
                assert "status" in health_data, "/api/health missing status field"
                _print(PASS, "/api/health returns structured checks payload")
        except Exception:
            failures += 1
            _print(FAIL, "One or more core routes failed")
            traceback.print_exc()

        try:
            wt = appmod._get_watchtower()
            assert wt._thread is not None and wt._thread.is_alive()
            first_wt_ident = wt._thread.ident
            appmod._ensure_background_services_started(app)
            assert wt._thread.ident == first_wt_ident
            _print(PASS, "Background service startup is lazy and idempotent")
        except Exception:
            failures += 1
            _print(FAIL, "Background service startup/idempotency check failed")
            traceback.print_exc()

    if failures:
        _print(FAIL, f"Smoke test completed with {failures} failing check(s)")
        return 1

    _print(PASS, "Smoke test completed successfully")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
