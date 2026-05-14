from __future__ import annotations

import unittest

from tests.common import ROOT  # noqa: F401
from agents_make.app_pool import (
    _check_dependencies,
    _check_vue_api_usage,
    _check_vue_bindings,
    _deterministic_vue_slots,
    _deterministic_readme_feature_list,
    _readme_slot_is_placeholder,
    _readme_slot_is_unreliable,
    _replace_raw_hex_with_neu_vars,
    _extract_slot_string,
    _feature_present,
    _json_contract_validator,
)
from agents_make.canon.app_spec import AppSpec


class MakeAuditHelperTests(unittest.TestCase):
    def test_local_db_import_is_not_reported_as_missing_dependency(self) -> None:
        present, missing = _check_dependencies("from db import get_db\nfrom flask import Flask\n")
        self.assertNotIn("db", present)
        self.assertNotIn("db", missing)

    def test_vue_binding_checker_understands_return_spreads(self) -> None:
        app_js = """
        createApp({
          setup() {
            const loading = ref(false);
            const stateBindings = { loading };
            const methodBindings = {};
            const items = ref([]);
            stateBindings.items = items;
            async function loadItems() {}
            methodBindings.loadItems = loadItems;
            return { ...stateBindings, ...methodBindings };
          }
        }).mount("#app");
        """
        html = '<div id="app"><button @click="loadItems">{{ items.length }} {{ loading }}</button></div>'
        self.assertEqual(_check_vue_bindings(html, app_js), [])

    def test_vue_binding_checker_ignores_object_literal_keys(self) -> None:
        app_js = """
        createApp({
          setup() {
            const item = ref({});
            function updateItem(payload) {}
            return { item, updateItem };
          }
        }).mount("#app");
        """
        html = '<button @click="updateItem({ title: item.title, archived: false })">{{ item.title }}</button>'
        self.assertEqual(_check_vue_bindings(html, app_js), [])

    def test_vue_api_usage_flags_collection_property_reads(self) -> None:
        spec = AppSpec.model_validate(
            {
                "app_name": "Bookmarks",
                "feature_summary": "Bookmarks",
                "entities": [{"name": "bookmark", "fields": [{"name": "title", "type": "str"}]}],
                "routes": [{"method": "GET", "path": "/api/bookmarks", "handler_name": "list_bookmarks", "entity": "bookmark"}],
                "views": [{"name": "bookmarks"}],
                "notes": "",
            }
        )
        app_js = """
        async function loadBookmarks() {
          const response = await apiFetch("/api/bookmarks");
          bookmarks.value = response.bookmarks;
        }
        """
        self.assertTrue(_check_vue_api_usage(app_js, spec))

    def test_deterministic_vue_slots_choose_owned_plant_dashboard(self) -> None:
        spec = AppSpec.model_validate(
            {
                "app_name": "Plant Care",
                "feature_summary": "Plant care with sign up, login, and overdue watering",
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
                    {"method": "POST", "path": "/api/plants", "handler_name": "create_plant", "entity": "plant"},
                ],
                "views": [{"name": "dashboard", "entity": "plant"}],
                "notes": "",
            }
        )
        slots = _deterministic_vue_slots(spec)
        joined = "\n".join(slots.values())
        self.assertIn("signupForm", joined)
        self.assertIn("loginForm", joined)
        self.assertIn("/api/plants?user_id=", joined)
        self.assertIn("overduePlants", joined)
        self.assertIn("needs-water", joined)
        self.assertIn('v-model="plant.name"', joined)
        self.assertNotIn('v-model="user.', joined)

    def test_feature_present_handles_mvp_language(self) -> None:
        frontend = '<input v-model="plant.species" /><span>{{ overduePlants.length }}</span>'
        backend = "CREATE TABLE plants (last_watered TEXT NOT NULL, species TEXT);"
        self.assertTrue(_feature_present("optional species", frontend))
        self.assertTrue(_feature_present("dashboard", frontend, backend))
        self.assertTrue(_feature_present("MVP", frontend, backend))
        self.assertTrue(_feature_present("highlight any plant whose last_watered date is more than 7 days ago", frontend, backend))

    def test_markdown_readme_slots_accept_lists(self) -> None:
        value = _extract_slot_string({"feature_list": ["Sign up", "Plant dashboard"]}, "feature_list", coerce_markdown_list=True)
        self.assertEqual(value, "- Sign up\n- Plant dashboard")

    def test_css_normalizer_replaces_named_colors(self) -> None:
        css = _replace_raw_hex_with_neu_vars(".x {\n  color: white;\n  background-color: red;\n}")
        self.assertIn("var(--neu-text-primary)", css)
        self.assertIn("var(--neu-bg-secondary)", css)
        self.assertNotIn("white", css)
        self.assertNotIn("red", css)

    def test_deterministic_readme_feature_list_replaces_placeholder(self) -> None:
        spec = AppSpec.model_validate(
            {
                "app_name": "Plant Care",
                "feature_summary": "Plant care",
                "entities": [
                    {"name": "user", "fields": [{"name": "email", "type": "str"}]},
                    {"name": "plant", "fields": [{"name": "last_watered", "type": "date"}]},
                ],
                "routes": [
                    {"method": "POST", "path": "/api/signup", "handler_name": "signup", "entity": None},
                    {"method": "POST", "path": "/api/login", "handler_name": "login", "entity": None},
                    {"method": "GET", "path": "/api/plants", "handler_name": "list_plants", "entity": "plant"},
                ],
                "views": [{"name": "dashboard", "entity": "plant"}],
                "notes": "",
            }
        )
        self.assertTrue(_readme_slot_is_placeholder("- No feature details added yet."))
        self.assertTrue(_readme_slot_is_unreliable("- User authentication with Flask-Login"))
        features = _deterministic_readme_feature_list(spec)
        self.assertIn("sign up", features)
        self.assertIn("last_watered", features)

    def test_json_contract_validator_maps_aliases(self) -> None:
        validator = _json_contract_validator(
            "make_app_api_slot",
            must_include=("imports_extra", "routes_extra"),
            aliases={"imports_extra": ("imports_feature",), "routes_extra": ("routes_feature",)},
        )
        raw = '{"imports_feature":"from x import y","routes_feature":"@app.get(\\"/api/x\\")"}'
        self.assertIsNone(validator(raw))

    def test_json_contract_validator_rejects_missing_required_keys(self) -> None:
        validator = _json_contract_validator(
            "make_app_vue_slot",
            must_include=("state", "methods", "computed", "on_mounted", "view_feature", "head_feature"),
        )
        error = validator('{"state":"x","methods":"y"}')
        self.assertIsInstance(error, str)
        self.assertIn("missing required keys", str(error).lower())


if __name__ == "__main__":
    unittest.main()
