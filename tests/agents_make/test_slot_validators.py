from __future__ import annotations

import unittest

from tests.common import ROOT  # noqa: F401
from agents_make.canon.slot_validators import validate_slot


class SlotValidatorTests(unittest.TestCase):
    def test_routes_rejects_data_literal(self) -> None:
        violations = validate_slot("app.py", "routes-feature", "[{'path': '/x'}]")
        self.assertTrue(any(v.rule == "slot_data_literal" for v in violations))

    def test_routes_accepts_route_function(self) -> None:
        code = '@app.get("/api/x")\ndef list_x():\n    return ok_items([])\n'
        violations = validate_slot("app.py", "routes-feature", code)
        self.assertEqual(violations, [])

    def test_imports_enforces_import_nodes_only(self) -> None:
        violations = validate_slot("app.py", "imports-feature", "x = 1")
        self.assertTrue(any(v.rule == "non_import" for v in violations))

    def test_imports_rejects_sqlalchemy_dependency(self) -> None:
        violations = validate_slot(
            "app.py",
            "imports-feature",
            "from flask_sqlalchemy import SQLAlchemy",
        )
        self.assertTrue(any(v.rule == "forbidden_dependency" for v in violations))

    def test_schema_rejects_postgres_serial(self) -> None:
        sql = "CREATE TABLE pets (id SERIAL PRIMARY KEY);"
        violations = validate_slot("schema.sql", "tables", sql)
        self.assertTrue(any(v.rule == "postgres_syntax" for v in violations))

    def test_schema_rejects_varchar(self) -> None:
        sql = "CREATE TABLE IF NOT EXISTS pets (name VARCHAR(255));"
        violations = validate_slot("schema.sql", "tables", sql)
        self.assertTrue(any(v.rule == "varchar_unnecessary" for v in violations))

    def test_schema_requires_if_not_exists(self) -> None:
        sql = "CREATE TABLE pets (id INTEGER PRIMARY KEY AUTOINCREMENT);"
        violations = validate_slot("schema.sql", "tables", sql)
        self.assertTrue(any(v.rule == "missing_if_not_exists" for v in violations))

    def test_schema_accepts_sqlite_table(self) -> None:
        sql = "CREATE TABLE IF NOT EXISTS pets (id INTEGER PRIMARY KEY AUTOINCREMENT);"
        violations = validate_slot("schema.sql", "tables", sql)
        self.assertEqual(violations, [])

    def test_js_state_reactive_requirement(self) -> None:
        violations = validate_slot("static/app.js", "state", "const x = 1;")
        self.assertTrue(any(v.rule == "no_reactive_binding" for v in violations))

    def test_js_methods_function_requirement(self) -> None:
        violations = validate_slot("static/app.js", "methods", "const x = 1;")
        self.assertTrue(any(v.rule == "no_function_def" for v in violations))

    def test_js_computed_requirement(self) -> None:
        violations = validate_slot("static/app.js", "computed", "const x = 1;")
        self.assertTrue(any(v.rule == "no_computed" for v in violations))

    def test_js_on_mounted_requirement(self) -> None:
        violations = validate_slot("static/app.js", "on-mounted", "const x = 1;")
        self.assertTrue(any(v.rule == "no_on_mounted" for v in violations))

    def test_html_view_must_start_with_tag(self) -> None:
        violations = validate_slot("templates/index.html", "view-feature", "hello")
        self.assertTrue(any(v.rule == "not_html" for v in violations))

    def test_css_requires_rule_blocks(self) -> None:
        violations = validate_slot("static/styles.css", "feature-styles", "body color red")
        self.assertTrue(any(v.rule == "no_rules" for v in violations))

    def test_seed_plaintext_password_rejected(self) -> None:
        sql = "INSERT INTO users (password_hash) VALUES ('password_hash_1');"
        violations = validate_slot("schema.sql", "seeds", sql)
        self.assertTrue(any(v.rule == "plaintext_password" for v in violations))

    def test_seed_hashed_password_accepted(self) -> None:
        sql = "INSERT INTO users (username, password_hash) VALUES ('test', 'pbkdf2:sha256:600000$seed$abc123');"
        violations = validate_slot("schema.sql", "seeds", sql)
        self.assertEqual(violations, [])


if __name__ == "__main__":
    unittest.main()
