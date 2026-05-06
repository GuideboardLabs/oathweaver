from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from tests.common import ensure_runtime  # noqa: F401
from cag.contradiction_detector import ContradictionDetector
from cag.decision_ledger import DecisionLedger
from cag.memory_store import CAGMemoryStore
from cag.promotion_gate import PromotionGate
from cag.selector import ScopedSelector


class Phase3CagCoreTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory(prefix="phase3_cag_core_")
        self.repo_root = Path(self.tmp.name)
        ensure_runtime(self.repo_root)
        self.store = CAGMemoryStore(self.repo_root)
        self.selector = ScopedSelector()
        self.detector = ContradictionDetector()
        self.gate = PromotionGate()
        self.ledger = DecisionLedger(self.repo_root)

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def test_memory_store_persists_required_fields_and_supports_supersession(self) -> None:
        first = self.store.add_row(
            {
                "text": "Use deterministic pipeline stages for research.",
                "scope": "level=thread|domain=computer_science|topic=programming|thread=thread_a|project=proj|run=run_1",
                "scope_level": "thread",
                "domain": "computer_science",
                "topic": "programming",
                "thread": "thread_a",
                "project": "proj",
                "run": "run_1",
                "type": "decision",
                "status": "accepted",
                "evidence": [{"kind": "citation", "value": "doc-1"}],
                "confidence": 0.8,
                "human_status": "unreviewed",
                "tags": ["pipeline", "deterministic"],
                "promoted_terms": ["pipeline", "deterministic"],
                "validation": {"task_metadata": True, "has_citation": True},
            }
        )
        second = self.store.add_row(
            {
                "text": "Prefer deterministic pipeline stages with strict contracts.",
                "scope": first["scope"],
                "scope_level": "thread",
                "domain": "computer_science",
                "topic": "programming",
                "thread": "thread_a",
                "project": "proj",
                "run": "run_2",
                "type": "decision",
                "status": "accepted",
                "evidence": [{"kind": "citation", "value": "doc-2"}],
                "confidence": 0.9,
                "human_status": "accepted",
                "tags": ["pipeline"],
                "promoted_terms": ["contracts"],
                "validation": {"task_metadata": True, "has_citation": True},
            }
        )

        self.store.mark_supersession(old_memory_id=first["memory_id"], new_memory_id=second["memory_id"])

        first_latest = self.store.get_row(first["memory_id"])
        assert first_latest is not None
        self.assertEqual(first_latest["status"], "superseded")
        self.assertIn(second["memory_id"], first_latest["superseded_by"])

    def test_selector_uses_scoped_weighting(self) -> None:
        rows = [
            {
                "memory_id": "m1",
                "text": "Pipeline stages can be deterministic.",
                "scope": "project",
                "tags": ["pipeline"],
                "promoted_terms": ["deterministic"],
            },
            {
                "memory_id": "m2",
                "text": "Deterministic pipeline with contract audits is required.",
                "scope": "project",
                "tags": ["pipeline", "contracts"],
                "promoted_terms": ["deterministic", "contracts"],
            },
        ]
        chosen, scores = self.selector.retrieve_scoped(
            task={
                "title": "Need deterministic pipeline design",
                "prompt": "Use deterministic pipeline and contract checks",
                "tags": ["pipeline", "contracts"],
                "continuity_terms": [
                    {"accepted_terms": ["deterministic", "contract"]},
                ],
            },
            rows=rows,
            k=2,
            return_scores=True,
        )
        self.assertEqual(chosen[0]["memory_id"], "m2")
        self.assertEqual(scores[0]["memory_id"], "m2")
        self.assertGreater(scores[0]["score"], scores[1]["score"])

    def test_contradiction_detector_and_budget(self) -> None:
        candidate = {
            "text": "We must disable cloud APIs for this project.",
            "scope_level": "project",
            "supersedes": [],
        }
        existing = [
            {
                "memory_id": "m1",
                "text": "We must enable cloud APIs for this project.",
                "scope_level": "project",
                "status": "accepted",
            }
        ]
        contradictions = self.detector.detect(candidate=candidate, existing_rows=existing)
        self.assertTrue(any(row.get("label") == "error" for row in contradictions))

        budget = self.detector.contradiction_budget(contradictions=contradictions, non_error_budget=0)
        self.assertFalse(budget["exceeded"])

    def test_promotion_gate_accepts_valid_candidate(self) -> None:
        decision = self.gate.evaluate(
            candidate={
                "text": "Use local-only inference for this runtime.",
                "scope": "level=project|domain=cs|topic=runtime|thread=t1|project=proj|run=r1",
                "scope_level": "project",
                "type": "constraint",
                "status": "candidate",
                "human_status": "unreviewed",
                "tags": ["runtime", "local"],
                "promoted_terms": ["local-only"],
                "validation": {"task_metadata": True, "has_citation": True},
                "evidence": [{"kind": "citation", "value": "source-1"}],
                "confidence": 0.8,
            },
            existing_rows=[],
            contradictions=[],
            contradiction_budget={"non_error_budget": 3, "non_error_count": 0, "exceeded": False},
        )
        row = decision.as_dict()
        self.assertTrue(row["accepted"])
        self.assertEqual(row["normalized_candidate"]["status"], "accepted")

    def test_decision_ledger_tracks_accepted_decision_rows(self) -> None:
        memory = self.store.add_row(
            {
                "text": "Adopt deterministic stage order in research pipeline.",
                "scope": "level=thread|domain=cs|topic=runtime|thread=t1|project=proj|run=r3",
                "scope_level": "thread",
                "domain": "cs",
                "topic": "runtime",
                "thread": "t1",
                "project": "proj",
                "run": "r3",
                "type": "decision",
                "status": "accepted",
                "evidence": [{"kind": "citation", "value": "source-3"}],
                "confidence": 0.85,
                "human_status": "accepted",
                "tags": ["pipeline"],
                "promoted_terms": ["deterministic"],
                "validation": {"task_metadata": True, "has_citation": True},
            }
        )
        entry = self.ledger.add_entry(memory_row=memory, rationale="Promoted by gate", status="accepted")
        assert entry is not None
        rows = self.ledger.list_entries(project="proj")
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["memory_id"], memory["memory_id"])


if __name__ == "__main__":
    unittest.main()
