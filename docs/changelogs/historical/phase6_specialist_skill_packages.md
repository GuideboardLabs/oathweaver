# Phase 6 Specialist Skill Packages

Phase 6 introduces specialist skill-pack modules and switches stage specialist resolution from hardcoded stage-only mapping to intersection-derived specialist assignment.

## Added specialist package system

- `SourceCode/specialists/_skill_pack_schema.py`
  - Defines `SpecialistSkillPack` and required package fields:
    - `role_prompt`
    - `output_schema`
    - `cag_query_profile`
    - `retrieval_evidence_template`
    - `few_shot_library`
    - `tool_permissions`
    - `verifier_rubric`
    - `optional_adapter`
    - `next_stage`

- `SourceCode/specialists/{planner,researcher,skeptic,synthesizer,verifier,memory_critic,auditor}/`
  - Each folder exposes a `build_pack(...)` function implementing a v1 deterministic skill package.

- `SourceCode/specialists/__init__.py`
  - Provides:
    - `specialist_roster()`
    - `derive_specialist_role(...)`
    - `build_specialist_pack(...)`
  - Supports intersection-derived aliases (for example `runtime_architect`, `memory_systems_analyst`, `benchmark_designer`, `code_reviewer`, `systems_skeptic`) mapped onto the initial v1 roster packs.

## Registry integration

- `SourceCode/scheduler/specialist_registry/registry.py`
  - Now derives specialist role using:
    - `Domain + Make Type + Research Focus + Pipeline Stage`
  - Builds manifests from skill packs instead of stage-only hardcoded defaults.

## Validation

- Added `tests/test_phase6_specialist_skill_packs.py` to verify:
  - required roster exists,
  - each core pack validates against required fields,
  - intersection-based derivation behaves as expected,
  - registry returns derived role + package-backed manifest values.
