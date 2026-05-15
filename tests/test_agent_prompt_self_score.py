from __future__ import annotations

import unittest

from tests.common import ROOT  # noqa: F401
from agents_research.deep_researcher import _agent_prompt


class AgentPromptSelfScoreTests(unittest.TestCase):
    def test_self_score_instructions_include_literal_example_and_no_heading_guard(self) -> None:
        system_prompt, _user_prompt = _agent_prompt(
            question="How should I train recall?",
            persona="critical_analyst",
            directive="Focus on evidence quality.",
            learned_guidance="",
            web_context="",
        )
        self.assertIn("Literal example to copy", system_prompt)
        self.assertIn(
            "SELF_SCORE: confidence=0.82; coverage=0.71; notes=good coverage but weak on legal edge cases",
            system_prompt,
        )
        self.assertIn("Do NOT output a heading like '# Self Score' or '## Self Score'.", system_prompt)
        self.assertIn("The final line must start with 'SELF_SCORE:'", system_prompt)

    def test_self_score_section_requires_one_line_machine_readable_format(self) -> None:
        system_prompt, _ = _agent_prompt(
            question="How should I train recall?",
            persona="critical_analyst",
            directive="Focus on evidence quality.",
            learned_guidance="",
            web_context="",
        )
        self.assertIn("MUST match this exact format", system_prompt)
        self.assertIn("confidence and coverage are floats between 0.0 and 1.0", system_prompt)


if __name__ == "__main__":
    unittest.main()
