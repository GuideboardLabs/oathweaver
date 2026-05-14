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

    def test_spec_generator_rejects_string_list_entities_without_fields(self) -> None:
        """Bare-string entity lists carry no field info — system should reject, not silently
        fabricate {id, name}-only entities that produce empty scaffolds."""
        from agents_make.app_pool import SpecConcretenessFailure
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
            with self.assertRaises(SpecConcretenessFailure):
                _step_spec_generator(client=None, question="Build a recipe app", research_knowledge="")

    def test_spec_generator_rejects_empty_entity_fields(self) -> None:
        """An entity with empty fields should be rejected, not silently filled with {id, name}.
        {id, name} is not a real domain spec — it indicates the LLM gave up and the system
        should regenerate or fail loudly rather than produce a useless scaffold."""
        from agents_make.app_pool import SpecConcretenessFailure
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
            with self.assertRaises(SpecConcretenessFailure):
                _step_spec_generator(client=None, question="Build users app", research_knowledge="")

    def test_spec_generator_deduplicates_repaired_fields(self) -> None:
        raw = json.dumps(
            {
                "app_name": "field_tracker",
                "feature_summary": "Track field names and field notes",
                "entities": [{"name": "garden_log", "attributes": ["id", "field", "field", "notes"]}],
                "routes": [{"path": "/api/garden_logs", "method": "POST", "handler_name": "create_garden_log"}],
                "views": [{"name": "garden-logs"}],
                "notes": "",
            }
        )
        with patch("agents_make.app_pool._chat", return_value=raw):
            spec = _step_spec_generator(client=None, question="Build field tracker", research_knowledge="")
        garden_log = next(entity for entity in spec.entities if entity.name == "garden_log")
        field_names = [field.name for field in garden_log.fields]
        self.assertEqual(field_names.count("field"), 1)

    def test_spec_generator_enriches_fields_from_request(self) -> None:
        raw = json.dumps(
            {
                "app_name": "bookmark_tracker",
                "feature_summary": "Save bookmarks with title, url, tags, notes, priority, and archived status.",
                "entities": [{"name": "bookmark", "fields": [{"name": "name", "type": "str"}]}],
                "routes": [{"path": "/api/bookmarks", "method": "POST", "handler_name": "create_bookmark"}],
                "views": [{"name": "dashboard"}],
                "notes": "",
            }
        )
        with patch("agents_make.app_pool._chat", return_value=raw):
            spec = _step_spec_generator(
                client=None,
                question="Build a bookmark tracker with title, url, tags, notes, priority, and archived status",
                research_knowledge="",
            )
        bookmark = next(entity for entity in spec.entities if entity.name == "bookmark")
        field_names = {field.name for field in bookmark.fields}
        for expected in {"title", "url", "tags", "notes", "priority", "archived"}:
            self.assertIn(expected, field_names)
        self.assertNotIn("name", field_names)

    def test_spec_generator_normalizes_plant_auth_owned_records(self) -> None:
        raw = json.dumps(
            {
                "app_name": "plant_care_app",
                "feature_summary": "Plant care app for users and plants.",
                "entities": [
                    {"name": "user", "fields": [{"name": "id", "type": "int"}, {"name": "plants", "type": "str"}]},
                    {"name": "plant", "fields": [{"name": "id", "type": "int"}, {"name": "name", "type": "str"}]},
                ],
                "routes": [{"path": "/api/users", "method": "GET", "handler_name": "list_users", "entity": "user"}],
                "views": [{"name": "dashboard", "entity": "user"}],
                "notes": "",
            }
        )
        question = (
            "Build a plant care tracker web app MVP. Users sign up and log in. "
            "Each user has plants. Each plant has a name, an optional species, and a last_watered date. "
            "The dashboard lists the logged-in user's plants and highlights any plant whose last_watered date is more than 7 days ago."
        )
        with patch("agents_make.app_pool._chat", return_value=raw):
            spec = _step_spec_generator(client=None, question=question, research_knowledge="")
        user = next(entity for entity in spec.entities if entity.name == "user")
        plant = next(entity for entity in spec.entities if entity.name == "plant")
        self.assertEqual({field.name for field in user.fields}, {"id", "email", "password_hash"})
        plant_fields = {field.name for field in plant.fields}
        for expected in {"user_id", "name", "species", "last_watered"}:
            self.assertIn(expected, plant_fields)
        self.assertNotIn("date", plant_fields)
        routes = {(route.method, route.path, route.entity or "") for route in spec.routes}
        self.assertIn(("POST", "/api/signup", ""), routes)
        self.assertIn(("POST", "/api/login", ""), routes)
        self.assertIn(("GET", "/api/plants", "plant"), routes)


if __name__ == "__main__":
    unittest.main()
