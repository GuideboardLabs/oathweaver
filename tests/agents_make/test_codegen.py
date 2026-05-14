from __future__ import annotations

import ast
import sqlite3
import unittest

from tests.common import ROOT  # noqa: F401
from agents_make.canon.app_spec import AppSpec
from agents_make.canon.codegen import render_imports, render_routes, render_schema


class CodegenTests(unittest.TestCase):
    def _spec(self) -> AppSpec:
        return AppSpec.model_validate(
            {
                "app_name": "Recipe Tracker",
                "feature_summary": "recipes",
                "entities": [
                    {
                        "name": "recipe",
                        "fields": [
                            {"name": "title", "type": "str", "required": True},
                            {"name": "password_hash", "type": "str", "required": False},
                            {"name": "created_at", "type": "datetime", "required": False},
                        ],
                        "primary_key": "id",
                    }
                ],
                "routes": [
                    {"method": "GET", "path": "/api/recipes", "handler_name": "list_recipes", "entity": "recipe", "summary": "list"},
                    {"method": "POST", "path": "/api/recipes", "handler_name": "create_recipe", "entity": "recipe", "summary": "create"},
                    {"method": "GET", "path": "/api/recipes/<int:id>", "handler_name": "get_recipe", "entity": "recipe", "summary": "get"},
                    {"method": "PUT", "path": "/api/recipes/<int:id>", "handler_name": "update_recipe", "entity": "recipe", "summary": "update"},
                    {"method": "DELETE", "path": "/api/recipes/<int:id>", "handler_name": "delete_recipe", "entity": "recipe", "summary": "delete"},
                ],
                "views": [{"name": "main-panel", "entity": "recipe", "purpose": "manage"}],
                "notes": "",
            }
        )

    def test_render_imports_adds_werkzeug_for_password(self) -> None:
        imports = render_imports(self._spec())
        self.assertIn("werkzeug.security", imports)

    def test_render_routes_are_valid_python(self) -> None:
        routes = render_routes(self._spec())
        ast.parse(routes)
        self.assertIn("@app.get(\"/api/recipes\")", routes)
        self.assertIn("def create_recipe", routes)

    def test_render_schema_is_sqlite_safe(self) -> None:
        tables, seeds = render_schema(self._spec())
        self.assertIn("CREATE TABLE IF NOT EXISTS", tables)
        self.assertIn("INTEGER PRIMARY KEY AUTOINCREMENT", tables)
        self.assertNotIn("SERIAL", tables)
        for statement in [s.strip() for s in tables.split(";") if s.strip()]:
            self.assertTrue(sqlite3.complete_statement(statement + ";"))
        if seeds:
            self.assertNotIn("changeme", seeds)

    def test_render_routes_includes_non_entity_endpoints(self) -> None:
        spec = AppSpec.model_validate(
            {
                "app_name": "Habit Tracker",
                "feature_summary": "habits and login",
                "entities": [
                    {
                        "name": "habit",
                        "fields": [{"name": "name", "type": "str", "required": True}],
                        "primary_key": "id",
                    }
                ],
                "routes": [
                    {"method": "POST", "path": "/api/login", "handler_name": "login_user", "entity": "", "summary": "login"},
                    {"method": "GET", "path": "/api/logs", "handler_name": "list_logs", "entity": "", "summary": "logs"},
                ],
                "views": [{"name": "dashboard", "entity": "habit", "purpose": "show"}],
                "notes": "",
            }
        )
        routes = render_routes(spec)
        ast.parse(routes)
        self.assertIn("@app.post(\"/api/login\")", routes)
        self.assertIn("def login_user()", routes)
        self.assertIn("@app.get(\"/api/logs\")", routes)

    def test_render_routes_handles_id_only_entity_without_invalid_sql(self) -> None:
        spec = AppSpec.model_validate(
            {
                "app_name": "Minimal Records",
                "feature_summary": "id-only records",
                "entities": [
                    {
                        "name": "record",
                        "fields": [{"name": "id", "type": "int", "required": True}],
                        "primary_key": "id",
                    }
                ],
                "routes": [
                    {"method": "POST", "path": "/api/records", "handler_name": "create_record", "entity": "record", "summary": "create"},
                    {"method": "PUT", "path": "/api/records/<int:id>", "handler_name": "update_record", "entity": "record", "summary": "update"},
                ],
                "views": [{"name": "dashboard", "entity": "record", "purpose": "show"}],
                "notes": "",
            }
        )
        routes = render_routes(spec)
        ast.parse(routes)
        self.assertIn("INSERT INTO records DEFAULT VALUES", routes)
        self.assertNotIn("INSERT INTO records () VALUES ()", routes)
        self.assertNotIn("UPDATE records SET  WHERE id = ?", routes)

    def test_render_routes_supports_auth_and_owned_collections(self) -> None:
        spec = AppSpec.model_validate(
            {
                "app_name": "Plant Care",
                "feature_summary": "Plant care",
                "entities": [
                    {
                        "name": "user",
                        "fields": [
                            {"name": "id", "type": "int", "required": True},
                            {"name": "email", "type": "str", "required": True},
                            {"name": "password_hash", "type": "str", "required": True},
                        ],
                    },
                    {
                        "name": "plant",
                        "fields": [
                            {"name": "id", "type": "int", "required": True},
                            {"name": "user_id", "type": "int", "required": False},
                            {"name": "name", "type": "str", "required": True},
                            {"name": "species", "type": "str", "required": False},
                            {"name": "last_watered", "type": "date", "required": True},
                        ],
                    },
                ],
                "routes": [
                    {"method": "POST", "path": "/api/signup", "handler_name": "signup", "entity": ""},
                    {"method": "POST", "path": "/api/login", "handler_name": "login", "entity": ""},
                    {"method": "GET", "path": "/api/plants", "handler_name": "list_plants", "entity": "plant"},
                ],
                "views": [{"name": "dashboard", "entity": "plant"}],
                "notes": "",
            }
        )
        imports = render_imports(spec)
        routes = render_routes(spec)
        ast.parse(imports + "\n" + routes)
        self.assertIn("generate_password_hash", imports)
        self.assertIn("check_password_hash", routes)
        self.assertIn("@app.post(\"/api/signup\")", routes)
        self.assertIn("@app.post(\"/api/login\")", routes)
        self.assertIn('request.args.get("user_id", type=int)', routes)
        self.assertIn("WHERE user_id = ?", routes)

    def test_app_spec_accepts_json_null_for_non_entity_route(self) -> None:
        spec = AppSpec.model_validate(
            {
                "app_name": "Auth",
                "feature_summary": "auth",
                "entities": [{"name": "user", "fields": [{"name": "email", "type": "str"}]}],
                "routes": [{"method": "POST", "path": "/api/login", "handler_name": "login", "entity": None}],
                "views": [{"name": "dashboard", "entity": None}],
                "notes": "",
            }
        )
        self.assertIsNone(spec.routes[0].entity)
        self.assertIsNone(spec.views[0].entity)


if __name__ == "__main__":
    unittest.main()
