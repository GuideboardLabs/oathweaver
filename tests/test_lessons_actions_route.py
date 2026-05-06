from __future__ import annotations

import os
import shutil
import unittest
from datetime import datetime, timezone
from pathlib import Path

from tests.common import ROOT, ensure_runtime
from shared_tools.db import connect, transaction


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


class LessonsActionsRouteTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        os.environ.setdefault("OATHWEAVER_OWNER_PASSWORD", "test-password")
        os.environ.setdefault("OATHWEAVER_AUTH_ENABLED", "0")
        from web_gui import app as appmod

        cls.appmod = appmod

    def setUp(self) -> None:
        self.runtime_tmp = Path(ROOT) / "Runtime" / "test_lessons_actions_route"
        if self.runtime_tmp.exists():
            shutil.rmtree(self.runtime_tmp, ignore_errors=True)
        self.repo_root = self.runtime_tmp / "repo"
        self.repo_root.mkdir(parents=True, exist_ok=True)
        ensure_runtime(self.repo_root)

        self.original_root = self.appmod.ROOT
        self.original_background = self.appmod._ensure_background_services_started
        self.appmod.ROOT = self.repo_root
        self.appmod._ensure_background_services_started = lambda _app=None: None
        self.app = self.appmod.create_app()

    def tearDown(self) -> None:
        self.appmod.ROOT = self.original_root
        self.appmod._ensure_background_services_started = self.original_background
        shutil.rmtree(self.runtime_tmp, ignore_errors=True)

    def _insert_lesson(
        self,
        *,
        lesson_id: str,
        origin_type: str,
        status: str = "candidate",
        active: int = 0,
        confidence: float = 0.92,
    ) -> None:
        ts = _now_iso()
        with connect(self.repo_root) as conn, transaction(conn, immediate=True):
            conn.execute(
                """
                INSERT INTO lessons(
                    id, lane, project, summary, guidance, origin_type, source, status,
                    confidence, active, approved_by, created_at, updated_at, expires_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
                """.strip(),
                (
                    lesson_id,
                    "research",
                    "general",
                    f"Summary for {lesson_id}",
                    "Trigger: drafting\nDo: include specifics\nAvoid: generic statements",
                    origin_type,
                    "test",
                    status,
                    confidence,
                    active,
                    "owner" if status == "approved" else None,
                    ts,
                    ts,
                    None,
                ),
            )

    def test_approve_candidate_manual_feedback(self) -> None:
        lesson_id = "lsn_route_approve_1"
        self._insert_lesson(lesson_id=lesson_id, origin_type="manual_feedback", status="candidate", active=0)
        with self.app.test_client() as client:
            resp = client.post(f"/api/lessons/{lesson_id}/approve")
            self.assertEqual(resp.status_code, 200)
            payload = resp.get_json()
            self.assertTrue(payload.get("ok"))
            row = payload.get("lesson", {})
            self.assertEqual(row.get("status"), "approved")
            self.assertEqual(int(row.get("active", 0)), 1)

    def test_approve_cloud_critique_is_policy_blocked(self) -> None:
        lesson_id = "lsn_route_blocked_1"
        self._insert_lesson(lesson_id=lesson_id, origin_type="cloud_critique", status="candidate", active=0)
        with self.app.test_client() as client:
            resp = client.post(f"/api/lessons/{lesson_id}/approve")
            self.assertEqual(resp.status_code, 400)
            payload = resp.get_json()
            self.assertFalse(payload.get("ok"))
            row = payload.get("lesson", {})
            self.assertTrue(bool(row.get("policy_blocked", False)))
            self.assertEqual(row.get("status"), "candidate")

    def test_reject_and_expire_routes(self) -> None:
        reject_id = "lsn_route_reject_1"
        expire_id = "lsn_route_expire_1"
        self._insert_lesson(lesson_id=reject_id, origin_type="manual_feedback", status="approved", active=1)
        self._insert_lesson(lesson_id=expire_id, origin_type="manual_feedback", status="approved", active=1)
        with self.app.test_client() as client:
            reject_resp = client.post(f"/api/lessons/{reject_id}/reject")
            self.assertEqual(reject_resp.status_code, 200)
            reject_row = reject_resp.get_json().get("lesson", {})
            self.assertEqual(reject_row.get("status"), "rejected")
            self.assertEqual(int(reject_row.get("active", 0)), 0)

            expire_resp = client.post(f"/api/lessons/{expire_id}/expire")
            self.assertEqual(expire_resp.status_code, 200)
            expire_row = expire_resp.get_json().get("lesson", {})
            self.assertEqual(expire_row.get("status"), "expired")
            self.assertEqual(int(expire_row.get("active", 0)), 0)
            self.assertTrue(str(expire_row.get("expires_at", "")).strip())


if __name__ == "__main__":
    unittest.main()
