from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
import unittest

from tests.common import ROOT  # noqa: F401  # ensure SourceCode on sys.path
from orchestrator.main import OathweaverOrchestrator


class _DummyGeneralPool:
    def query(self, _text: str, n: int = 4) -> list[str]:
        _ = n
        return []

    def save(self, _key: str, _value: str) -> None:
        return None


class _DummyOllama:
    def __init__(self) -> None:
        self.last_call: dict[str, object] = {}

    def chat(self, **kwargs):
        self.last_call = dict(kwargs)
        return "stub reply"


class ConversationReplyProjectBriefsTests(unittest.TestCase):
    def setUp(self) -> None:
        orch = OathweaverOrchestrator.__new__(OathweaverOrchestrator)
        orch.repo_root = Path(ROOT)
        orch.project_slug = "alpha"
        orch.manifesto_path = orch.repo_root / "Runtime" / "config" / "oathweaver_manifesto.md"
        orch._manifesto_cache_mtime = -1.0
        orch._manifesto_cache_text = ""
        orch._project_research_brief_cache = {}
        orch._project_make_brief_cache = {}
        orch.ollama = _DummyOllama()
        orch._infra = SimpleNamespace(
            general_pool=_DummyGeneralPool(),
            pipeline_store=SimpleNamespace(get=lambda _slug: {"topic_type": "general"}),
            topic_memory=SimpleNamespace(get_context_for_query=lambda _query: ""),
            library_service=SimpleNamespace(context_text=lambda *_args, **_kwargs: ""),
            learning_engine=SimpleNamespace(guidance_for_lane=lambda *_args, **_kwargs: ""),
            project_memory=SimpleNamespace(
                ingest_text=lambda *_args, **_kwargs: None,
                summary_text=lambda *_args, **_kwargs: "",
            ),
            watchtower=None,
        )

        orch._chat_layer_config = lambda: {
            "model": "stub-model",
            "temperature": 0.2,
            "num_ctx": 4096,
            "timeout_sec": 30,
            "retry_attempts": 1,
            "retry_backoff_sec": 0.1,
            "fallback_models": [],
            "think": False,
        }
        orch._weaver_persona_block = lambda: "Persona block"
        orch._strip_oathweaver_vocative_prefix = lambda text: str(text)
        orch._is_oathweaver_self_query = lambda _text: False
        orch._capture_daymarker_reminder = lambda _text: ""
        orch._capture_daymarker_event = lambda _text, history=None: ""
        orch._is_reminder_only_request = lambda _text: False
        orch._is_event_only_request = lambda _text: False
        orch._is_lightweight_social = lambda _text: False
        orch._is_casual_conversation_turn = lambda _text: False
        orch._is_recency_sensitive = lambda _text: False
        orch._is_evolving_topic = lambda _text: False
        orch._is_recency_sensitive_from_history = lambda _history: False
        orch._contextual_live_query = lambda text, _prior: str(text)
        orch._requires_live_verification = lambda _text, _topic: False
        orch._should_offer_web = lambda _text, _lane: False
        orch._routing_context_gate = lambda _text, _prior, trigger_reason="keyword": True
        orch._context_bundle_for_query = lambda _text, household_chars=0: ("", "", "")
        orch._extract_rejected_tool = lambda _text: ""
        orch._watchtower_context_for_query = lambda: ""
        orch._surface_polish_reply = lambda text: str(text)
        orch._dedup_forage_tags = lambda text: str(text)
        orch._append_daymarker_note = lambda reply, note: f"{reply}\n{note}" if str(note).strip() else str(reply)
        orch._context_feedback = lambda **_kwargs: ""
        orch._run_continuous_improvement = lambda **_kwargs: None
        orch._maybe_auto_refresh_project_facts = lambda _history: None
        orch._project_research_brief = lambda project_slug, query, max_chars=1200: {
            "brief": f"Research summaries for project {project_slug}:\n- 2026-04-22: research summary line",
            "raw_excerpts": ["first raw excerpt", "second raw excerpt", "third raw excerpt"],
            "query": query,
        }
        orch._project_make_brief = lambda project_slug, max_items=5, max_chars=900: (
            f"Recent Make outputs for project {project_slug}:\n"
            "- [Guide] Team onboarding guide (2026-04-23): concise preview"
        )
        self.orch = orch

    def test_conversation_prompt_includes_project_research_and_make_briefs(self) -> None:
        reply = self.orch.conversation_reply(
            "How should we continue this project?",
            history=[{"role": "user", "content": "Use our prior work."}],
            project="alpha",
        )
        self.assertEqual(reply, "stub reply")

        system_prompt = str(self.orch.ollama.last_call.get("system_prompt", ""))
        self.assertIn("Research summaries for project alpha:", system_prompt)
        self.assertIn("Raw research excerpts for project alpha:", system_prompt)
        self.assertIn("first raw excerpt", system_prompt)
        self.assertIn("second raw excerpt", system_prompt)
        self.assertNotIn("third raw excerpt", system_prompt)
        self.assertIn("Recent Make outputs for project alpha:", system_prompt)


if __name__ == "__main__":
    unittest.main()
