from __future__ import annotations

import unittest
from pathlib import Path

from tests.common import ROOT  # noqa: F401
from orchestrator.main import OathweaverOrchestrator


class ResearchArtifactLinkTests(unittest.TestCase):
    def _host(self) -> OathweaverOrchestrator:
        host = OathweaverOrchestrator.__new__(OathweaverOrchestrator)
        host.repo_root = Path(ROOT)
        return host

    def test_research_artifacts_block_uses_markdown_file_links(self) -> None:
        host = self._host()
        out = {
            "summary_path": str(Path(ROOT) / "Projects" / "demo" / "research_summaries" / "summary with space.md"),
            "raw_path": str(Path(ROOT) / "Projects" / "demo" / "research_raw" / "raw-notes.md"),
            "critique_path": str(Path(ROOT) / "Projects" / "demo" / "research_summaries" / "critique.md"),
            "web_details": {
                "source_path": str(Path(ROOT) / "Projects" / "demo" / "research_sources" / "sources.md"),
            },
        }
        block = host._format_research_artifacts_block(out)
        self.assertIn(
            "[summary with space.md](/api/files/read?path=Projects/demo/research_summaries/summary%20with%20space.md)",
            block,
        )
        self.assertIn(
            "[raw-notes.md](/api/files/read?path=Projects/demo/research_raw/raw-notes.md)",
            block,
        )
        self.assertIn(
            "[critique.md](/api/files/read?path=Projects/demo/research_summaries/critique.md)",
            block,
        )
        self.assertIn(
            "[sources.md](/api/files/read?path=Projects/demo/research_sources/sources.md)",
            block,
        )

    def test_make_summary_reply_open_artifact_link_is_url_quoted(self) -> None:
        host = self._host()
        out = {
            "ok": True,
            "path": str(Path(ROOT) / "Projects" / "demo" / "Content" / "guide with spaces.md"),
            "delivery_kind": "guide",
            "message": "Guide complete.",
        }
        reply = host._make_summary_reply(lane="make_longform", out=out, fallback="fallback")
        self.assertIn(
            "[Open artifact](/api/files/read?path=Projects/demo/Content/guide%20with%20spaces.md)",
            reply,
        )


if __name__ == "__main__":
    unittest.main()
