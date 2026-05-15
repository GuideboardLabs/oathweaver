from __future__ import annotations

import logging
import unittest
from unittest.mock import patch

from tests.common import ROOT  # noqa: F401
from agents_research import deep_researcher


class DeepResearcherLoggingTests(unittest.TestCase):
    def test_module_exposes_logger_for_error_paths(self) -> None:
        self.assertTrue(hasattr(deep_researcher, "LOGGER"))
        self.assertIsInstance(deep_researcher.LOGGER, logging.Logger)

    def test_uncatalogued_topic_type_logs_warning_and_falls_back_to_general_profile(self) -> None:
        with patch.object(deep_researcher.LOGGER, "warning") as warn:
            profile = deep_researcher._analysis_profile_for_type("not_a_real_topic")  # type: ignore[attr-defined]
        self.assertEqual(profile, deep_researcher.ANALYSIS_PROFILE_GENERAL)
        warn.assert_called_once()

    def test_sanitize_model_list_removes_retired_model_and_deduplicates(self) -> None:
        models = deep_researcher._sanitize_model_list(  # type: ignore[attr-defined]
            ["qwen3:4b", "qwen3:8b", "qwen3:8b", "", None, "deepseek-r1:8b"]
        )
        self.assertEqual(models, ["qwen3:8b", "deepseek-r1:8b"])


if __name__ == "__main__":
    unittest.main()
