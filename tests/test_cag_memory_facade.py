from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from tests.common import ensure_runtime  # noqa: F401
from shared_tools.cag_memory_facade import CAGMemoryFacade, MemoryRecord


class CagMemoryFacadeTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory(prefix="cag_memory_facade_")
        self.repo_root = Path(self.tmp.name)
        ensure_runtime(self.repo_root)

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def _seed_topic_memory(self) -> None:
        topics_dir = self.repo_root / "Runtime" / "memory" / "topics"
        topics_dir.mkdir(parents=True, exist_ok=True)
        now = "2026-05-13T12:00:00+00:00"
        topic_payload = {
            "key": "llm_runtime",
            "title": "LLM Runtime",
            "subtopics": ["scheduler", "context windows"],
            "facts": [
                {
                    "id": "f_runtime_1",
                    "claim": "Scheduler warm-pools reduce cold-start latency in constrained local runtimes.",
                    "confidence": 0.92,
                    "status": "canon",
                    "project": "general",
                    "created_at": now,
                    "updated_at": now,
                }
            ],
            "updated_at": now,
        }
        index_payload = {
            "topics": {
                "llm_runtime": {
                    "key": "llm_runtime",
                    "title": "LLM Runtime",
                    "subtopics": ["scheduler", "context windows"],
                    "fact_count": 1,
                    "canon_count": 1,
                    "updated_at": now,
                }
            }
        }
        (topics_dir / "llm_runtime.json").write_text(json.dumps(topic_payload, indent=2), encoding="utf-8")
        (self.repo_root / "Runtime" / "memory" / "topic_index.json").write_text(
            json.dumps(index_payload, indent=2),
            encoding="utf-8",
        )

    def test_conflict_resolution_prefers_higher_score(self) -> None:
        newer = MemoryRecord(
            category="semantic",
            key="decision:planner",
            value="Use staged planner budget for runtime lane.",
            source_score=0.2,
            confidence=0.8,
            updated_at="2026-05-13T12:00:00+00:00",
            conflict_key="planner:budget",
        )
        older = MemoryRecord(
            category="semantic",
            key="decision:planner",
            value="Use planner budget.",
            source_score=0.05,
            confidence=0.6,
            updated_at="2026-04-01T12:00:00+00:00",
            conflict_key="planner:budget",
        )
        resolved, conflicts = CAGMemoryFacade.resolve_semantic_conflicts([older, newer])
        self.assertEqual(len(resolved), 1)
        self.assertEqual(resolved[0].value, newer.value)
        self.assertEqual(len(conflicts), 1)

    def test_topic_memory_records_feed_semantic_recall(self) -> None:
        self._seed_topic_memory()
        facade = CAGMemoryFacade(self.repo_root)
        topic_rows = facade._records_from_topic_memory("llm runtime scheduler context")
        self.assertTrue(topic_rows)
        self.assertTrue(any(row.source == "topic_memory" for row in topic_rows))

        recall = facade.recall(
            "How should runtime scheduler context be handled?",
            kinds=("semantic",),
            project="general",
        )
        semantic_rows = recall.get("results", {}).get("semantic", [])
        self.assertTrue(semantic_rows)
        self.assertTrue(any(str(row.get("source", "")) == "topic_memory" for row in semantic_rows))


if __name__ == "__main__":
    unittest.main()
