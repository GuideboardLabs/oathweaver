from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from flask import Flask

from tests.common import ensure_runtime  # noqa: F401  # ensure SourceCode on sys.path
from web_gui.routes.projects import create_projects_blueprint


class _FakeActivityStore:
    def __init__(self, rows: list[dict]) -> None:
        self._rows = list(rows)

    def rows(self) -> list[dict]:
        return list(self._rows)


class _FakeOrch:
    def __init__(self, repo_root: Path, rows: list[dict]) -> None:
        self.repo_root = repo_root
        self.activity_store = _FakeActivityStore(rows)


class _FakeCtx:
    def __init__(self, orch: _FakeOrch) -> None:
        self._orch = orch

    def require_profile(self) -> dict[str, str]:
        return {"id": "p1"}

    def new_orch(self, _profile: dict[str, str]) -> _FakeOrch:
        return self._orch


class MakeOutputsEndpointTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmpdir = tempfile.TemporaryDirectory(prefix="oathweaver_make_outputs_")
        self.repo_root = Path(self.tmpdir.name)
        ensure_runtime(self.repo_root)
        self.project_slug = "alpha"
        base = self.repo_root / "Projects" / self.project_slug / "Essays-Scripts" / self.project_slug
        base.mkdir(parents=True, exist_ok=True)

        essay_path = base / "20260421_120000_future_of_ai.md"
        essay_path.write_text("# Essay\n", encoding="utf-8")
        guide_path = base / "20260423_083000_team_onboarding_guide.md"
        guide_path.write_text("# Guide\n", encoding="utf-8")
        guide_raw = base / "20260423_083000_team_onboarding_guide_raw.md"
        guide_raw.write_text("raw guide draft", encoding="utf-8")
        tool_path = base / "20260422_070000_script_tool.md"
        tool_path.write_text("print('x')\n", encoding="utf-8")

        rows = [
            {
                "ts": "2026-04-21T12:00:00+00:00",
                "event": "make_deliverable_written",
                "details": {
                    "project": self.project_slug,
                    "make_type": "essay_long",
                    "topic": "Future of AI",
                    "summary_path": str(essay_path),
                    "request_id": "req-essay",
                },
            },
            {
                "ts": "2026-04-22T07:00:00+00:00",
                "event": "make_deliverable_written",
                "details": {
                    "project": self.project_slug,
                    "make_type": "tool",
                    "summary_path": str(tool_path),
                    "request_id": "req-tool",
                },
            },
            {
                "ts": "2026-04-23T08:30:00+00:00",
                "event": "make_deliverable_written",
                "details": {
                    "project": self.project_slug,
                    "kind": "guide",
                    "summary_path": str(guide_path),
                },
            },
            {
                "ts": "2026-04-23T09:00:00+00:00",
                "event": "make_deliverable_written",
                "details": {
                    "project": "other-project",
                    "make_type": "guide",
                    "summary_path": str(guide_path),
                    "request_id": "req-other",
                },
            },
        ]
        self.ctx = _FakeCtx(_FakeOrch(self.repo_root, rows))
        app = Flask(__name__)
        app.register_blueprint(create_projects_blueprint(self.ctx))
        self.client = app.test_client()

    def tearDown(self) -> None:
        self.tmpdir.cleanup()

    def test_lists_only_prose_outputs_sorted_desc(self) -> None:
        response = self.client.get("/api/projects/Alpha/make_outputs?limit=40")
        self.assertEqual(response.status_code, 200)
        payload = response.get_json() or {}
        self.assertEqual(payload.get("project"), self.project_slug)

        outputs = payload.get("outputs") or []
        self.assertEqual(len(outputs), 2)
        self.assertEqual(outputs[0]["make_type"], "guide")
        self.assertEqual(outputs[0]["request_id"], "activity:2")
        self.assertEqual(outputs[0]["title"], "team onboarding guide")
        self.assertEqual(outputs[0]["make_label"], "Guide")
        self.assertEqual(outputs[0]["category"], "writing")
        self.assertTrue(str(outputs[0]["summary_path"]).startswith("Projects/alpha/"))
        self.assertTrue(str(outputs[0]["raw_path"]).endswith("_raw.md"))

        self.assertEqual(outputs[1]["make_type"], "essay_long")
        self.assertEqual(outputs[1]["request_id"], "req-essay")
        self.assertEqual(outputs[1]["title"], "Future of AI")
        self.assertNotIn("tool", [row.get("make_type") for row in outputs])


if __name__ == "__main__":
    unittest.main()
