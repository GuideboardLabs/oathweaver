from __future__ import annotations

import shutil
import unittest
from pathlib import Path

from tests.common import ROOT
from benchmark.context_usage_eval import run_context_usage_eval
from shared_tools.context_policy import analyze_query_context, build_context_usage_guidance, evaluate_context_use
from shared_tools.continuous_improvement import ContinuousImprovementEngine


class ContextPolicyTests(unittest.TestCase):
    def test_analyze_query_context_detects_family_hints_without_personal_flags(self) -> None:
        general = analyze_query_context("Explain how heat pumps work.")
        self.assertFalse(general["family_query"])

        family_plan = analyze_query_context("What should I be paying attention to this week for the kids?")
        self.assertTrue(family_plan["family_query"])

    def test_context_guidance_includes_non_intrusive_rules(self) -> None:
        analysis = analyze_query_context("What should I remember about our travel plans?")
        guidance = build_context_usage_guidance(analysis, personal_available=True)
        self.assertIn("Use retrieved personal context only when it materially improves the answer.", guidance)
        self.assertIn("Do not say you remembered something", guidance)

    def test_evaluate_context_use_penalizes_intrusive_mentions(self) -> None:
        feedback = evaluate_context_use(
            "Explain how heat pumps work.",
            "I remembered from your memory that you like concise answers.",
            personal_context_available=True,
            personal_context_injected=True,
        )
        self.assertEqual(feedback["outcome"], "mixed")
        self.assertLess(feedback["score"], 0.72)
        self.assertTrue(any("intrusive_context_mention" in note for note in feedback["notes"]))

    def test_continuous_improvement_tracks_context_score(self) -> None:
        import tempfile
        runtime_tmp = Path(tempfile.mkdtemp(prefix="oathweaver_test_context_policy_"))
        repo_root = runtime_tmp / "repo"
        repo_root.mkdir(parents=True, exist_ok=True)
        engine = ContinuousImprovementEngine(repo_root)
        evaluation = engine.evaluate_turn(
            user_text="What should I remember this week for the kids?",
            assistant_text="You have a packed week and should front-load school prep.",
            lane="project",
            worker_result=None,
            context_feedback={"score": 0.9, "notes": ["context_used_well"]},
        )
        engine.note_turn(
            project="general",
            lane="project",
            quality_score=evaluation["score"],
            context_score=evaluation["context_score"],
            outcome=evaluation["outcome"],
            notes=evaluation["notes"],
        )
        status = engine.status_snapshot("general")
        self.assertGreater(status["project"]["avg_context_quality"], 0.0)
        shutil.rmtree(runtime_tmp, ignore_errors=True)

    def test_context_usage_eval_dataset_passes(self) -> None:
        payload = run_context_usage_eval(Path(ROOT))
        self.assertTrue(payload["ok"], msg=str(payload))


if __name__ == "__main__":
    unittest.main()
