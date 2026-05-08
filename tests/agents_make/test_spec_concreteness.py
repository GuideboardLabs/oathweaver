from __future__ import annotations

import unittest

from tests.common import ROOT  # noqa: F401
from agents_make.app_pool import _validate_spec_concreteness
from agents_make.canon.app_spec import AppSpec


class SpecConcretenessTests(unittest.TestCase):
    def test_meta_prompt_like_spec_rejected(self) -> None:
        spec = AppSpec.model_validate(
            {
                "app_name": "X",
                "feature_summary": "Build the true MVP of this application with context",
                "entities": [{"name": "build", "fields": [{"name": "name", "type": "str"}], "primary_key": "id"}],
                "routes": [{"method": "GET", "path": "/api/builds", "handler_name": "list_builds", "entity": "build", "summary": "List"}],
                "views": [{"name": "build-list", "entity": "build", "purpose": "show"}],
                "notes": "",
            }
        )
        issues = _validate_spec_concreteness(spec, "Build the true MVP")
        self.assertTrue(issues)
        self.assertTrue(any("abstract" in issue or "generic" in issue for issue in issues))

    def test_concrete_spec_accepted(self) -> None:
        spec = AppSpec.model_validate(
            {
                "app_name": "Recipe Tracker",
                "feature_summary": "Users save recipes with ingredients and instructions",
                "entities": [
                    {"name": "user", "fields": [{"name": "username", "type": "str"}], "primary_key": "id"},
                    {"name": "recipe", "fields": [{"name": "title", "type": "str"}], "primary_key": "id"},
                ],
                "routes": [{"method": "GET", "path": "/api/recipes", "handler_name": "list_recipes", "entity": "recipe", "summary": "List"}],
                "views": [{"name": "recipe-list", "entity": "recipe", "purpose": "show"}],
                "notes": "",
            }
        )
        self.assertEqual(_validate_spec_concreteness(spec, "Build recipe tracker"), [])

    def test_id_only_entity_rejected(self) -> None:
        spec = AppSpec.model_validate(
            {
                "app_name": "Recipe Tracker",
                "feature_summary": "Users save recipes with ingredients and instructions",
                "entities": [
                    {
                        "name": "recipe",
                        "fields": [{"name": "id", "type": "int", "required": True}],
                        "primary_key": "id",
                    }
                ],
                "routes": [
                    {
                        "method": "GET",
                        "path": "/api/recipes",
                        "handler_name": "list_recipes",
                        "entity": "recipe",
                        "summary": "List",
                    }
                ],
                "views": [{"name": "recipe-list", "entity": "recipe", "purpose": "show"}],
                "notes": "",
            }
        )
        issues = _validate_spec_concreteness(spec, "Build a recipe app")
        self.assertTrue(any("no fields beyond id" in issue for issue in issues))


if __name__ == "__main__":
    unittest.main()
