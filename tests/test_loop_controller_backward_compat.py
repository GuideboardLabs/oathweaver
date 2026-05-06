from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from tests.common import ensure_runtime  # noqa: F401  # ensure SourceCode on sys.path
from shared_tools.loop_controller import run_draft_critique_revise


class _NoopClient:
    def chat(self, **kwargs):  # noqa: ANN003
        _ = kwargs
        return "noop"

    def release_model(self, model: str) -> None:
        _ = model


def _write_routing(repo_root: Path, payload: dict) -> None:
    path = repo_root / "SourceCode" / "configs" / "model_routing.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


class LoopControllerBackwardCompatTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmpdir = tempfile.TemporaryDirectory(prefix="oathweaver_loop_backcompat_")
        self.repo_root = Path(self.tmpdir.name)
        ensure_runtime(self.repo_root)
        _write_routing(
            self.repo_root,
            {
                "synthesis": {
                    "tier_default": {"model": "qwen3:8b"},
                    "escalation_policy": {
                        "enabled": False,
                        "severity_min": 3,
                        "max_revise_loops": 2,
                    },
                }
            },
        )
        self.client = _NoopClient()

    def tearDown(self) -> None:
        self.tmpdir.cleanup()

    def test_disabled_policy_matches_single_pass_behavior(self) -> None:
        def _single_pass(text: str, _tier_cfg: dict) -> tuple[str, str, dict]:
            return f"{text}\n\nsingle-pass-revised", "single-pass-critique", {"severity": 2}

        direct_revised, direct_log, _sev = _single_pass("fixture draft", {})
        result = run_draft_critique_revise(
            repo_root=self.repo_root,
            lane_key="synthesis",
            draft_fn=lambda _tier_cfg: "fixture draft",
            critique_fn=_single_pass,
            importance="medium",
            client=self.client,
            telemetry_ctx={"task_class": "backcompat"},
        )

        self.assertEqual(result.final_text, direct_revised)
        self.assertEqual(result.critique_logs[-1], direct_log)
        self.assertFalse(result.premium_activated)
        self.assertEqual(result.tier_used_final, "default")


if __name__ == "__main__":
    unittest.main()
