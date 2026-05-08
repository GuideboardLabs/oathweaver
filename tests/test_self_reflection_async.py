from __future__ import annotations

import tempfile
import time
import unittest
from pathlib import Path

from tests.common import ensure_runtime
from shared_tools.self_reflection import SelfReflectionEngine


class _NoopClient:
    def chat(self, **_kwargs):  # pragma: no cover - should not be called in these tests
        raise RuntimeError("chat should not be called")


class _LearningOk:
    def __init__(self, delay_sec: float = 0.2) -> None:
        self.delay_sec = delay_sec

    def ingest_feedback_text(self, **_kwargs):
        time.sleep(self.delay_sec)
        return {"lesson_ids": ["lesson_async_1"]}


class _LearningFail:
    def ingest_feedback_text(self, **_kwargs):
        source = str(_kwargs.get("source", "")).strip().lower()
        if source == "self_reflection_user":
            raise RuntimeError("simulated learning failure")
        return {"lesson_ids": []}


class SelfReflectionAsyncAnswerTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmpdir = tempfile.TemporaryDirectory(prefix="oathweaver_reflect_async_")
        self.repo_root = Path(self.tmpdir.name)
        ensure_runtime(self.repo_root)

    def tearDown(self) -> None:
        self.tmpdir.cleanup()

    def _build_engine(self, learning_engine) -> SelfReflectionEngine:
        return SelfReflectionEngine(
            self.repo_root,
            client=_NoopClient(),
            learning_engine=learning_engine,
            model_cfg={},
        )

    def test_answer_returns_before_learning_finishes(self) -> None:
        engine = self._build_engine(_LearningOk(delay_sec=0.4))
        cycle = engine.create_cycle(
            project="proj",
            lane="project",
            user_request="u",
            orchestrator_reply="r",
            worker_result={},
        )
        cycle_id = str(cycle.get("id", ""))

        started = time.monotonic()
        answered = engine.answer(cycle_id, "Use better source diversity.")
        elapsed = time.monotonic() - started

        self.assertIsNotNone(answered)
        self.assertLess(elapsed, 0.25)
        self.assertEqual(str((answered or {}).get("status", "")), "closed")
        self.assertEqual(str((answered or {}).get("learning_status", "")), "queued")

        deadline = time.monotonic() + 3.0
        final_cycle = None
        while time.monotonic() < deadline:
            final_cycle = engine.get_cycle(cycle_id)
            if str((final_cycle or {}).get("learning_status", "")).lower() == "completed":
                break
            time.sleep(0.05)
        self.assertIsNotNone(final_cycle)
        self.assertEqual(str((final_cycle or {}).get("learning_status", "")).lower(), "completed")
        self.assertEqual((final_cycle or {}).get("answer_lesson_ids", []), ["lesson_async_1"])

    def test_answer_records_learning_failure_without_reopening_cycle(self) -> None:
        engine = self._build_engine(_LearningFail())
        cycle = engine.create_cycle(
            project="proj",
            lane="project",
            user_request="u",
            orchestrator_reply="r",
            worker_result={},
        )
        cycle_id = str(cycle.get("id", ""))
        answered = engine.answer(cycle_id, "Try a stronger fallback.")
        self.assertEqual(str((answered or {}).get("status", "")), "closed")

        deadline = time.monotonic() + 2.0
        final_cycle = None
        while time.monotonic() < deadline:
            final_cycle = engine.get_cycle(cycle_id)
            if str((final_cycle or {}).get("learning_status", "")).lower() == "failed":
                break
            time.sleep(0.05)
        self.assertIsNotNone(final_cycle)
        self.assertEqual(str((final_cycle or {}).get("status", "")).lower(), "closed")
        self.assertEqual(str((final_cycle or {}).get("learning_status", "")).lower(), "failed")
        self.assertIn("simulated learning failure", str((final_cycle or {}).get("learning_error", "")))


if __name__ == "__main__":
    unittest.main()
