from __future__ import annotations

import json
import unittest
from pathlib import Path
from unittest.mock import patch

from tests.common import ROOT  # noqa: F401
from agents_make.app_pool import (
    SpecConcretenessFailure,
    SpecGenerationFailure,
    _step_spec_generator,
)


class SpecGeneratorFailureModeTests(unittest.TestCase):
    def test_spec_generator_raises_on_unparseable_json(self) -> None:
        with patch("agents_make.app_pool._chat", return_value="not json {["):
            with self.assertRaises(SpecGenerationFailure):
                _step_spec_generator(client=None, question="Build a recipe app", research_knowledge="")

    def test_spec_generator_rejects_generic_entity(self) -> None:
        bad = json.dumps(
            {
                "app_name": "Build Tracker",
                "feature_summary": "Build the true MVP with context",
                "entities": [
                    {
                        "name": "build",
                        "primary_key": "id",
                        "fields": [{"name": "name", "type": "str", "required": True}],
                    }
                ],
                "routes": [
                    {
                        "method": "GET",
                        "path": "/api/builds",
                        "handler_name": "list_builds",
                        "entity": "build",
                        "summary": "List builds",
                    }
                ],
                "views": [{"name": "build-list", "entity": "build", "purpose": "show builds"}],
                "notes": "",
            }
        )
        with patch("agents_make.app_pool._chat", return_value=bad):
            with self.assertRaises(SpecConcretenessFailure):
                _step_spec_generator(client=None, question="Build a recipe app", research_knowledge="")

    def test_no_default_app_spec_remains(self) -> None:
        src = Path(ROOT / "SourceCode" / "agents_make" / "app_pool.py").read_text(encoding="utf-8")
        self.assertNotIn("_default_app_spec", src)

    def test_spec_generator_repairs_noncanonical_payload_shape(self) -> None:
        raw = json.dumps(
            {
                "app_name": "habit_tracker",
                "feature_summary": "Habit tracker with login and streaks",
                "entities": [
                    {"entity_name": "user", "attributes": ["id", "username", "password_hash", "created_at"]},
                    {"entity_name": "habit", "attributes": ["id", "name", "category", "user_id", "created_at"]},
                ],
                "routes": [
                    {"route_path": "/api/users", "handler_name": "users_controller.index"},
                    {"route_path": "/api/habits/:id", "handler_name": "habits_controller.show"},
                ],
                "views": [{"view_name": "dashboard", "description": "Main dashboard"}],
                "notes": ["Use prior streak rules"],
            }
        )
        with patch("agents_make.app_pool._chat", return_value=raw):
            spec = _step_spec_generator(client=None, question="Build a habit tracker", research_knowledge="")
        names = [entity.name for entity in spec.entities]
        self.assertIn("user", names)
        self.assertIn("habit", names)
        self.assertTrue(any(route.handler_name == "users_controller_index" for route in spec.routes))

    def test_spec_generator_repairs_string_list_entities_and_views(self) -> None:
        raw = json.dumps(
            {
                "app_name": "recipe_sharing_app",
                "feature_summary": "A web app to share and store recipes with ingredients and instructions.",
                "entities": ["user", "recipe", "ingredient", "instruction"],
                "routes": [
                    {"path": "/api/users", "method": "GET", "handler_name": "get_users"},
                    {"path": "/api/recipes", "method": "POST", "handler_name": "create_recipe"},
                    {"path": "/api/instructions/<int:id>", "method": "GET", "handler_name": "get_instruction_by_id"},
                ],
                "views": ["add-recipe", "view-recipe"],
                "notes": ["Ensure entities are snake_case."],
            }
        )
        with patch("agents_make.app_pool._chat", return_value=raw):
            spec = _step_spec_generator(client=None, question="Build a recipe app", research_knowledge="")
        self.assertGreaterEqual(len(spec.entities), 3)
        self.assertTrue(any(entity.name == "recipe" for entity in spec.entities))
        self.assertTrue(any(view.name == "add-recipe" for view in spec.views))

    def test_spec_generator_repairs_empty_entity_fields_with_name_fallback(self) -> None:
        raw = json.dumps(
            {
                "app_name": "users_app",
                "feature_summary": "Manage user profiles, emails, and account names",
                "entities": [{"name": "user", "fields": []}],
                "routes": [{"path": "/api/users", "method": "POST", "handler_name": "create_user"}],
                "views": [{"name": "dashboard"}],
                "notes": "",
            }
        )
        with patch("agents_make.app_pool._chat", return_value=raw):
            spec = _step_spec_generator(client=None, question="Build users app", research_knowledge="")
        user_entity = next(entity for entity in spec.entities if entity.name == "user")
        field_names = [field.name for field in user_entity.fields]
        self.assertIn("id", field_names)
        self.assertIn("name", field_names)


if __name__ == "__main__":
    unittest.main()
