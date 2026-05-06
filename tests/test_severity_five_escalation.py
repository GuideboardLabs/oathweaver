from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from tests.common import ensure_runtime  # noqa: F401  # ensure SourceCode on sys.path
from shared_tools.loop_controller import run_draft_critique_revise


class _FakeClient:
    def __init__(self) -> None:
        self.released: list[str] = []

    def chat(self, **kwargs):  # noqa: ANN003
        _ = kwargs
        return "focus revised"

    def release_model(self, model: str) -> None:
        self.released.append(str(model))


def _write_routing(repo_root: Path, payload: dict) -> None:
    path = repo_root / "SourceCode" / "configs" / "model_routing.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


class SeverityFiveEscalationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmpdir = tempfile.TemporaryDirectory(prefix="oathweaver_severity5_")
        self.repo_root = Path(self.tmpdir.name)
        ensure_runtime(self.repo_root)
        _write_routing(
            self.repo_root,
            {
                "premium_models": ["deepseek-r1:14b"],
                "synthesis": {
                    "tier_default": {"model": "qwen3:8b", "timeout_sec": 60},
                    "tier_premium": {"model": "deepseek-r1:14b", "timeout_sec": 120, "keep_alive": "0"},
                    "escalation_policy": {
                        "enabled": True,
                        "importance_min": "high",
                        "severity_min": 3,
                        "max_premium_passes": 1,
                        "max_revise_loops": 0,
                        "require_prior_default_pass": True,
                        "cooloff_sec": 0,
                    },
                },
            },
        )
        self.client = _FakeClient()

    def tearDown(self) -> None:
        self.tmpdir.cleanup()

    def test_severity_five_high_importance_escalates_once_with_warning(self) -> None:
        calls: list[str] = []

        def _critique(text: str, tier_cfg: dict) -> tuple[str, str, dict]:
            model = str(tier_cfg.get("model", "")).strip()
            calls.append(model)
            if "14b" in model:
                return "premium consolidated", "premium critique", {"severity": 5, "revise_focus": []}
            return "default revised", "default critique", {"severity": 5, "revise_focus": []}

        result = run_draft_critique_revise(
            repo_root=self.repo_root,
            lane_key="synthesis",
            draft_fn=lambda _tier_cfg: "initial draft",
            critique_fn=_critique,
            importance="high",
            client=self.client,
            telemetry_ctx={"task_class": "research_synthesis"},
        )

        self.assertTrue(result.premium_activated)
        self.assertEqual(result.tier_used_final, "premium")
        self.assertEqual(result.final_text, "premium consolidated")
        self.assertTrue(result.warning_banner)
        self.assertEqual(calls.count("qwen3:8b"), 1)
        self.assertEqual(calls.count("deepseek-r1:14b"), 1)


if __name__ == "__main__":
    unittest.main()
