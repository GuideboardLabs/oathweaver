from __future__ import annotations

import importlib.util
import tempfile
import unittest
from pathlib import Path

from tests.common import ROOT  # noqa: F401
from agents_make.app_pool import _runtime_smoke_check
from agents_make.canon import copy_scaffold, write_slot
from agents_make.canon.app_spec import AppSpec
from agents_make.canon.codegen import render_imports, render_routes, render_schema


class RuntimeSmokeTests(unittest.TestCase):
    @staticmethod
    def _has_flask() -> bool:
        return importlib.util.find_spec("flask") is not None

    def _spec(self) -> AppSpec:
        return AppSpec.model_validate(
            {
                "app_name": "Todo",
                "feature_summary": "todo",
                "entities": [{"name": "todo", "fields": [{"name": "title", "type": "str", "required": True}], "primary_key": "id"}],
                "routes": [
                    {"method": "GET", "path": "/api/todos", "handler_name": "list_todos", "entity": "todo", "summary": "list"},
                    {"method": "POST", "path": "/api/todos", "handler_name": "create_todo", "entity": "todo", "summary": "create"},
                    {"method": "GET", "path": "/api/todos/<int:id>", "handler_name": "get_todo", "entity": "todo", "summary": "get"},
                    {"method": "PUT", "path": "/api/todos/<int:id>", "handler_name": "update_todo", "entity": "todo", "summary": "update"},
                    {"method": "DELETE", "path": "/api/todos/<int:id>", "handler_name": "delete_todo", "entity": "todo", "summary": "delete"},
                ],
                "views": [{"name": "todo-list", "entity": "todo", "purpose": "show"}],
                "notes": "",
            }
        )

    def test_runtime_smoke_passes_for_codegen_slots(self) -> None:
        if not self._has_flask():
            self.skipTest("flask is not installed in this test environment")
        with tempfile.TemporaryDirectory(prefix="runtime_codegen_") as tmp:
            app_dir = Path(tmp) / "app"
            copy_scaffold("web_app_v1", app_dir)
            spec = self._spec()
            imports = render_imports(spec)
            routes = render_routes(spec)
            tables, seeds = render_schema(spec)
            write_slot(app_dir / "app.py", "imports-feature", imports)
            write_slot(app_dir / "app.py", "routes-feature", routes)
            write_slot(app_dir / "schema.sql", "tables", tables)
            write_slot(app_dir / "schema.sql", "seeds", seeds)
            failures = _runtime_smoke_check(app_dir, spec)
            self.assertEqual(failures, [])

    def test_runtime_smoke_reports_missing_route(self) -> None:
        if not self._has_flask():
            self.skipTest("flask is not installed in this test environment")
        with tempfile.TemporaryDirectory(prefix="runtime_bad_route_") as tmp:
            app_dir = Path(tmp) / "app"
            copy_scaffold("web_app_v1", app_dir)
            spec = self._spec()
            tables, seeds = render_schema(spec)
            write_slot(app_dir / "schema.sql", "tables", tables)
            write_slot(app_dir / "schema.sql", "seeds", seeds)
            write_slot(
                app_dir / "app.py",
                "routes-feature",
                '@app.get("/api/not_todos")\ndef list_not_todos():\n    return ok_items([])',
            )
            failures = _runtime_smoke_check(app_dir, spec)
            self.assertTrue(any(str(row.get("route")) == "/api/todos" for row in failures))

    def test_runtime_smoke_tolerates_404_on_id_routes_when_records_absent(self) -> None:
        if not self._has_flask():
            self.skipTest("flask is not installed in this test environment")
        with tempfile.TemporaryDirectory(prefix="runtime_id404_ok_") as tmp:
            app_dir = Path(tmp) / "app"
            copy_scaffold("web_app_v1", app_dir)
            spec = AppSpec.model_validate(
                {
                    "app_name": "Minimal",
                    "feature_summary": "id only",
                    "entities": [{"name": "user", "fields": [], "primary_key": "id"}],
                    "routes": [
                        {"method": "GET", "path": "/api/users/<int:id>", "handler_name": "get_user", "entity": "user", "summary": "get"},
                        {"method": "PUT", "path": "/api/users/<int:id>", "handler_name": "update_user", "entity": "user", "summary": "update"},
                        {"method": "DELETE", "path": "/api/users/<int:id>", "handler_name": "delete_user", "entity": "user", "summary": "delete"},
                    ],
                    "views": [{"name": "users", "entity": "user", "purpose": "show"}],
                    "notes": "",
                }
            )
            imports = render_imports(spec)
            routes = render_routes(spec)
            tables, seeds = render_schema(spec)
            write_slot(app_dir / "app.py", "imports-feature", imports)
            write_slot(app_dir / "app.py", "routes-feature", routes)
            write_slot(app_dir / "schema.sql", "tables", tables)
            write_slot(app_dir / "schema.sql", "seeds", seeds)
            failures = _runtime_smoke_check(app_dir, spec)
            self.assertEqual(failures, [])


if __name__ == "__main__":
    unittest.main()
