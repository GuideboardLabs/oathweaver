#!/usr/bin/env python3
from __future__ import annotations

import os
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "SourceCode"
if str(SOURCE) not in sys.path:
    sys.path.insert(0, str(SOURCE))
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tests.common import ensure_runtime


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def _prepare_temp_root(temp_root: Path) -> None:
    if temp_root.exists():
        shutil.rmtree(temp_root, ignore_errors=True)
    temp_root.mkdir(parents=True, exist_ok=True)
    ensure_runtime(temp_root)


def main() -> int:
    os.environ.setdefault("OATHWEAVER_OWNER_PASSWORD", "smoke-test-password")
    os.environ.setdefault("OATHWEAVER_AUTH_ENABLED", "0")

    from web_gui import app as appmod

    temp_root = ROOT / "Runtime" / "test_ui_phase_smoke"
    if temp_root.exists():
        shutil.rmtree(temp_root, ignore_errors=True)
    try:
        _prepare_temp_root(temp_root)

        original_root = appmod.ROOT
        original_background = appmod._ensure_background_services_started
        appmod.ROOT = temp_root
        appmod._ensure_background_services_started = lambda _app=None: None
        try:
            flask_app = appmod.create_app()
            with flask_app.test_client() as client:
                root_html = client.get("/").get_data(as_text=True)
                _require("Personal Context" in root_html, "Personal Context panel missing from root page")
                _require("Memory Ledger" in root_html, "Memory Ledger missing from root page")
                _require("Memory Overview" in root_html, "Memory Overview section missing from root page")
                _require("Planner Pulse" not in root_html, "Planner UI still present in root page")
                _require("Waypoints" not in root_html, "Planner app/tab still present in root page")

                profile_resp = client.patch(
                    "/api/personal-memory/profile",
                    json={
                        "name": "Alex",
                        "preferred_name": "Alex",
                        "notes": "Parent of Mia and Scout caretaker.",
                    },
                )
                _require(profile_resp.status_code == 200, "Profile save failed")

                family_resp = client.post(
                    "/api/personal-memory/family",
                    json={
                        "name": "Mia",
                        "relationship": "daughter",
                        "notes": "Loves soccer.",
                    },
                )
                _require(family_resp.status_code == 201, "Family member create failed")

                pet_resp = client.post(
                    "/api/personal-memory/pets",
                    json={
                        "name": "Scout",
                        "animal_type": "dog",
                        "notes": "Needs vet follow-up.",
                    },
                )
                _require(pet_resp.status_code == 201, "Pet create failed")

                memory_payload = client.get("/api/personal-memory").get_json()
                _require(bool(memory_payload), "Personal memory payload missing")
                _require(
                    len(memory_payload.get("records", [])) >= 3,
                    "Structured memory records were not created",
                )

                records_payload = client.get("/api/personal-memory/records").get_json()
                _require(bool(records_payload and records_payload.get("records")), "Memory records endpoint returned no records")
                mia_record = next(
                    (
                        record
                        for record in records_payload["records"]
                        if str(record.get("subject", "")).strip().lower() == "mia"
                    ),
                    None,
                )
                _require(mia_record is not None, "Expected Mia memory record was not created")

                pin_resp = client.patch(f"/api/personal-memory/records/{mia_record['id']}/pin")
                _require(pin_resp.status_code == 200, "Pin memory action failed")

                explain_resp = client.post(
                    "/api/personal-memory/records/explain",
                    json={"id": mia_record["id"]},
                )
                explain_payload = explain_resp.get_json()
                _require(explain_resp.status_code == 200, "Explain memory action failed")
                _require(bool(explain_payload.get("record")), "Explain memory returned no record payload")

                planner_missing = client.get("/api/planner/state")
                _require(planner_missing.status_code in {404, 405}, "Planner API should be removed")

                second_brain_payload = client.get("/api/second-brain").get_json()
                _require(bool(second_brain_payload), "Second Brain payload missing")
                _require(bool(second_brain_payload.get("overview")), "Second Brain overview missing")
                _require(bool(second_brain_payload.get("briefing_lines")), "Second Brain briefing lines missing")
                _require(bool(second_brain_payload.get("timeline")), "Second Brain timeline missing")

            print("UI smoke passed: planner removal and core memory/system flows are healthy.")
            return 0
        finally:
            appmod.ROOT = original_root
            appmod._ensure_background_services_started = original_background
    finally:
        shutil.rmtree(temp_root, ignore_errors=True)


if __name__ == "__main__":
    raise SystemExit(main())
