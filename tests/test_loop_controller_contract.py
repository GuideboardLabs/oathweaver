from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from tests.common import ensure_runtime  # noqa: F401  # ensure SourceCode on sys.path
from shared_tools.loop_controller import run_draft_critique_revise


class _FakeClient:
    def __init__(self) -> None:
        self.calls: list[dict] = []
        self.released: list[str] = []

    def chat(self, **kwargs):
        self.calls.append(dict(kwargs))
        return "revised via focus"

    def release_model(self, model: str) -> None:
        self.released.append(str(model))


def _write_routing(repo_root: Path, payload: dict) -> None:
    path = repo_root / "SourceCode" / "configs" / "model_routing.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


class LoopControllerContractTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmpdir = tempfile.TemporaryDirectory(prefix="oathweaver_loop_controller_")
        self.repo_root = Path(self.tmpdir.name)
        ensure_runtime(self.repo_root)
        _write_routing(
            self.repo_root,
            {
                "synthesis": {
                    "tier_default": {"model": "qwen3:8b", "timeout_sec": 60, "retry_attempts": 1},
                    "escalation_policy": {
                        "enabled": False,
                        "severity_min": 3,
                        "max_revise_loops": 2,
                    },
                }
            },
        )
        self.client = _FakeClient()

    def tearDown(self) -> None:
        self.tmpdir.cleanup()

    def test_stops_when_severity_zero(self) -> None:
        result = run_draft_critique_revise(
            repo_root=self.repo_root,
            lane_key="synthesis",
            draft_fn=lambda _tier_cfg: "draft",
            critique_fn=lambda text, _tier_cfg: (f"{text} updated", "critique", {"severity": 0, "revise_focus": []}),
            importance="medium",
            client=self.client,
            telemetry_ctx={"task_class": "unit_test"},
        )
        self.assertEqual(result.loop_count, 1)
        self.assertEqual(result.tier_used_final, "default")
        self.assertFalse(result.premium_activated)
        self.assertIn("updated", result.final_text)

    def test_respects_max_revise_loops(self) -> None:
        _write_routing(
            self.repo_root,
            {
                "synthesis": {
                    "tier_default": {"model": "qwen3:8b", "timeout_sec": 60, "retry_attempts": 1},
                    "escalation_policy": {
                        "enabled": False,
                        "severity_min": 3,
                        "max_revise_loops": 2,
                    },
                }
            },
        )
        counter = {"n": 0}

        def _critique(text: str, _tier_cfg: dict) -> tuple[str, str, dict]:
            counter["n"] += 1
            return f"{text} v{counter['n']}", f"log {counter['n']}", {"severity": 4, "revise_focus": []}

        result = run_draft_critique_revise(
            repo_root=self.repo_root,
            lane_key="synthesis",
            draft_fn=lambda _tier_cfg: "draft",
            critique_fn=_critique,
            importance="medium",
            client=self.client,
            telemetry_ctx={"task_class": "unit_test"},
        )
        self.assertEqual(result.loop_count, 3)  # initial + 2 revise loops
        self.assertEqual(counter["n"], 3)

    def test_cancel_checker_honored(self) -> None:
        result = run_draft_critique_revise(
            repo_root=self.repo_root,
            lane_key="synthesis",
            draft_fn=lambda _tier_cfg: "draft",
            critique_fn=lambda text, _tier_cfg: (text, "log", {"severity": 4}),
            importance="medium",
            client=self.client,
            telemetry_ctx={"task_class": "unit_test"},
            cancel_checker=lambda: True,
        )
        self.assertEqual(result.loop_count, 0)
        self.assertEqual(result.escalation_reason, "cancelled")
        self.assertEqual(result.final_text, "draft")

    def test_emits_telemetry_rows(self) -> None:
        run_draft_critique_revise(
            repo_root=self.repo_root,
            lane_key="synthesis",
            draft_fn=lambda _tier_cfg: "draft",
            critique_fn=lambda text, _tier_cfg: (text, "critique", {"severity": 0}),
            importance="medium",
            client=self.client,
            telemetry_ctx={"task_class": "unit_test"},
        )
        critic_loops = self.repo_root / "Runtime" / "telemetry" / "critic_loops.jsonl"
        escalation = self.repo_root / "Runtime" / "telemetry" / "escalation_decisions.jsonl"
        self.assertTrue(critic_loops.exists())
        self.assertTrue(escalation.exists())
        self.assertGreater(len(critic_loops.read_text(encoding="utf-8").strip().splitlines()), 0)
        self.assertGreater(len(escalation.read_text(encoding="utf-8").strip().splitlines()), 0)


if __name__ == "__main__":
    unittest.main()
