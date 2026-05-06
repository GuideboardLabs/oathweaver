from __future__ import annotations

import unittest

from scheduler.specialist_registry import SpecialistRegistry
from specialists import build_specialist_pack, derive_specialist_role, specialist_roster
from specialists._skill_pack_schema import REQUIRED_PACK_FIELDS, validate_skill_pack


class Phase6SpecialistSkillPackTests(unittest.TestCase):
    def test_initial_roster_contains_required_specialists(self) -> None:
        roster = set(specialist_roster())
        required = {
            "planner",
            "researcher",
            "skeptic",
            "synthesizer",
            "verifier",
            "memory_critic",
            "auditor",
        }
        self.assertTrue(required.issubset(roster))

    def test_each_core_specialist_pack_has_required_shape(self) -> None:
        for specialist_id in sorted(specialist_roster()):
            pack = build_specialist_pack(
                specialist_id=specialist_id,
                pipeline_stage="architecture",
                next_stage="verification",
                domain="computer_science",
                make_type="model_runtime_system",
                research_focus="implementation_focused",
            )
            errors = validate_skill_pack(pack)
            self.assertEqual(errors, [], msg=f"{specialist_id} failed validation: {errors}")
            row = pack.as_dict()
            for key in REQUIRED_PACK_FIELDS:
                self.assertIn(key, row)

    def test_derivation_rule_uses_intersection_not_static_stage_only(self) -> None:
        runtime_arch_role = derive_specialist_role(
            stage="architecture",
            domain="computer_science",
            make_type="model_runtime_system",
            research_focus="implementation_focused",
        )
        self.assertEqual(runtime_arch_role, "runtime_architect")

        systems_skeptic_role = derive_specialist_role(
            stage="nuance_pass",
            domain="computer_science",
            make_type="model_runtime_system",
            research_focus="implementation_focused",
        )
        self.assertEqual(systems_skeptic_role, "systems_skeptic")

    def test_registry_uses_derived_role_and_pack_fields(self) -> None:
        registry = SpecialistRegistry()
        manifest = registry.manifest_for_stage(
            stage="architecture",
            pipeline="build_pipeline",
            next_stage="verification",
            domain="computer_science",
            make_type="model_runtime_system",
            research_focus="implementation_focused",
        )
        row = manifest.as_dict()
        self.assertEqual(row["specialist_role"], "runtime_architect")
        self.assertTrue(str(row["role_prompt"]).strip())
        self.assertTrue(str(row["output_schema"]).strip())
        self.assertTrue(str(row["cag_query_profile"]).strip())


if __name__ == "__main__":
    unittest.main()
