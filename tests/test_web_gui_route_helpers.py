from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

from tests.common import ROOT  # noqa: F401
from web_gui.routes import chat_message_utils as msg_utils
from web_gui.routes import chat_messages as msg_routes
from web_gui.routes import projects as project_routes
from web_gui.routes import system_support as support_routes


class _Rows:
    def __init__(self, rows):
        self._rows = rows

    def rows(self):
        return list(self._rows)


class _FakeCtx:
    def __init__(self, base: Path) -> None:
        self._base = base

    def attachment_dir_for(self, _profile: dict, conversation_id: str) -> Path:
        path = self._base / "Runtime" / "attachments" / conversation_id
        path.mkdir(parents=True, exist_ok=True)
        return path


class WebGuiRouteHelperTests(unittest.TestCase):
    def test_chat_message_utils_normalize_and_parse_loras(self) -> None:
        values = msg_utils.normalize_lora_selection(["alpha", "alpha", "beta", "", None])
        self.assertEqual(values, ["alpha", "beta"])
        self.assertEqual(msg_utils.parse_selected_loras_value('["x","x","y"]'), ["x", "y"])
        self.assertEqual(msg_utils.parse_selected_loras_value("x, y, x"), ["x", "y"])
        self.assertEqual(msg_utils.parse_selected_loras_value("["), [])

    def test_chat_message_utils_type_and_think_stream_helpers(self) -> None:
        self.assertTrue(msg_utils.to_bool("yes"))
        self.assertFalse(msg_utils.to_bool("off"))
        self.assertEqual(msg_utils.to_int("7"), 7)
        self.assertEqual(msg_utils.to_float("3.5"), 3.5)
        stream = msg_utils.build_message_think_stream(
            {
                "started_at": "2026-01-01T00:00:00+00:00",
                "updated_at": "2026-01-01T00:00:02+00:00",
                "events": [
                    {"ts": "2026-01-01T00:00:00+00:00", "stage": "queued", "detail": "start"},
                    {"ts": "2026-01-01T00:00:02+00:00", "stage": "done", "detail": "finish"},
                ],
            }
        )
        self.assertIsNotNone(stream)
        assert stream is not None
        self.assertEqual(len(stream["events"]), 2)
        self.assertGreaterEqual(float(stream["duration_sec"]), 2.0)

    def test_chat_message_utils_web_meta_and_optional_reads(self) -> None:
        with tempfile.TemporaryDirectory(prefix="web_meta_") as tmp:
            repo = Path(tmp)
            file_path = repo / "note.md"
            file_path.write_text("hello", encoding="utf-8")
            self.assertEqual(msg_utils.read_optional_text("note.md", repo_root=repo), "hello")
            self.assertEqual(msg_utils.truncate_utf8("abc", 2), "ab")
            meta = msg_utils.build_message_web_meta(
                web_stack={"source_count": 1},
                web_details={"sources": [{"url": "https://example.com", "domain": "example.com"}]},
                research_reply={"text": "ok", "sentences": [{"text": "one"}], "retrieved_chunks": []},
                think_stream={"events": [{"stage": "x"}]},
            )
            self.assertIsNotNone(meta)
            assert meta is not None
            self.assertIn("web_stack", meta)
            self.assertIn("research_reply", meta)
            self.assertIn("think_stream", meta)

    def test_chat_message_resolution_helpers(self) -> None:
        with tempfile.TemporaryDirectory(prefix="msg_resolution_") as tmp:
            repo = Path(tmp)
            summary = repo / "summary.md"
            summary.write_text("summary", encoding="utf-8")
            content = f"see /api/files/read?path={summary}"
            message = {"id": "m1", "role": "assistant", "mode": "talk", "content": content}
            path = msg_routes._message_summary_path(message, repo_root=repo)
            self.assertTrue(path.endswith("summary.md"))
            convo = {"messages": [message]}
            reply = msg_routes._resolve_reply_target(convo, {"id": "m1"}, repo_root=repo)
            self.assertIsNotNone(reply)
            self.assertEqual(reply["id"], "m1")

    def test_chat_message_output_seeding_and_strip_rules(self) -> None:
        with tempfile.TemporaryDirectory(prefix="msg_seed_") as tmp:
            repo = Path(tmp)
            summary = repo / "run_summary.md"
            raw = repo / "run_summary_raw.md"
            summary.write_text("Short summary", encoding="utf-8")
            raw.write_text("raw details", encoding="utf-8")
            rows = [
                {
                    "event": "make_deliverable_written",
                    "details": {
                        "project": "demo",
                        "request_id": "req_1",
                        "summary_path": str(summary),
                    },
                }
            ]
            orch = SimpleNamespace(activity_store=_Rows(rows), repo_root=repo)
            row = msg_routes._make_output_row_for_request_id(orch, "demo", "req_1")
            self.assertIsNotNone(row)
            seeded = msg_routes._seed_artifact_text_for_extension(orch, "demo", "req_1")
            self.assertIn("Prior output to extend", seeded)
            self.assertIn("raw output", seeded)
            stripped = msg_routes._strip_trailing_assistant_rule("hello\n***\n")
            self.assertEqual(stripped, "hello")

    def test_chat_message_scene_and_negative_prompt_helpers(self) -> None:
        prompt = "A person in front of a castle is on fire at night"
        self.assertTrue(msg_routes._is_simple_image_prompt("castle at dusk"))
        self.assertTrue(msg_routes._has_structured_scene_request(prompt))
        entities = msg_routes._extract_required_entities(prompt)
        self.assertIn("person", entities)
        self.assertIn("fortress", entities)
        conditions = msg_routes._extract_required_conditions(prompt)
        self.assertTrue(any("on fire" in item for item in conditions))
        scene_extras = msg_routes._scene_guidance_extras(prompt)
        self.assertTrue(scene_extras)
        neg = msg_routes._refine_negative_prompt("", prompt=prompt, preset_id="pastels")
        self.assertIn("split screen", neg)
        self.assertIn("source_furry", neg)

    def test_chat_message_refine_image_prompt_branches(self) -> None:
        prompt = "person in front of a burning castle at night"
        preset_expectations = {
            "foxo_slyesium": "ZaUm",
            "pixel_forge": "pixel art",
            "fhoxi": "chibi",
            "faceless_uwu": "anime minimalist",
            "nutshell": "Kurzgesagt",
            "foxs_moving_castle": "studio ghibli inspired style",
            "painterly": "brush stroke",
            "borderfox": "Akaburstyle",
            "uwu_figurine": "figure",
            "and_the_hound": "DisneyRenstyle",
            "realism": "film grain",
            "fixel": "score_9",
            "sketch_book": "pencil sketch",
            "shirt_designs": "T shirt design",
            "wallace_vomit": "claymation",
            "parchment": "on parchment",
            "foxjourney": "professional digital art",
            "unfinished_anime": "source_anime",
            "pastels": "pastel colors",
            "illustration": "flat illustration",
            "foxel": "voxel art",
            "storyboard": "storyboard sketch of",
            "fs1": "ps1 style",
            "lo_fi": "dreamyvibes artstyle",
            "ms_fainx": "MSPaint Portrait",
        }
        for preset, marker in preset_expectations.items():
            with self.subTest(preset=preset):
                text = msg_routes._refine_image_prompt(
                    prompt,
                    image_style="stylized",
                    selected_loras=["demo"],
                    has_references=True,
                    preset_id=preset,
                    refiner_profile={"night_terms": ["night"]},
                    scene_subject="character",
                )
                self.assertIn(marker, text)

    def test_chat_message_refine_image_prompt_subject_variants(self) -> None:
        subject_map = {
            "scene": "mountain castle at night with flames",
            "object": "ancient sword on fire",
            "character": "hero portrait at night",
        }
        preset_markers = {
            "pixel_forge": "pixel art",
            "fhoxi": "chibi",
            "faceless_uwu": "anime minimalist",
            "nutshell": "Kurzgesagt style",
            "foxs_moving_castle": "studio ghibli inspired style",
            "painterly": "brush stroke",
            "borderfox": "Akaburstyle",
            "uwu_figurine": "figure",
            "and_the_hound": "DisneyRenstyle",
            "realism": "film grain",
            "fixel": "score_9",
            "sketch_book": "pencil sketch",
            "shirt_designs": "T shirt design",
            "wallace_vomit": "claymation",
            "parchment": "on parchment",
            "foxjourney": "professional digital art",
            "unfinished_anime": "source_anime",
            "pastels": "pastel colors",
            "illustration": "flat illustration",
            "foxel": "voxel style",
            "storyboard": "storyboard sketch of",
            "fs1": "ps1 style",
            "lo_fi": "dreamyvibes artstyle",
        }
        for preset, marker in preset_markers.items():
            for subject, subject_prompt in subject_map.items():
                with self.subTest(preset=preset, subject=subject):
                    text = msg_routes._refine_image_prompt(
                        subject_prompt,
                        image_style="stylized",
                        selected_loras=[],
                        has_references=False,
                        preset_id=preset,
                        refiner_profile={"night_terms": ["night"]},
                        scene_subject=subject,
                    )
                    self.assertIn(marker, text)

    def test_chat_message_refine_negative_prompt_passthrough_and_structured(self) -> None:
        plain = msg_routes._refine_negative_prompt("bad anatomy", prompt="simple icon", preset_id="")
        self.assertEqual(plain, "bad anatomy")
        structured = msg_routes._refine_negative_prompt(
            "",
            prompt="a person in front of a castle is on fire",
            preset_id="and_the_hound",
        )
        self.assertIn("split screen", structured)
        self.assertIn("missing person", structured)

    def test_chat_message_scene_extractors_handle_empty_and_aliases(self) -> None:
        self.assertEqual(msg_routes._extract_required_entities(""), [])
        self.assertEqual(msg_routes._extract_required_conditions(""), [])
        self.assertEqual(msg_routes._canonical_entity_name("castle"), "fortress")
        self.assertEqual(msg_routes._canonical_entity_name("people"), "person")

    def test_project_helper_functions_cover_path_title_and_promote_mode(self) -> None:
        with tempfile.TemporaryDirectory(prefix="project_helpers_") as tmp:
            repo = Path(tmp)
            source = repo / "source"
            target = repo / "target"
            (source / "nested").mkdir(parents=True, exist_ok=True)
            (source / "nested" / "a.txt").write_text("a", encoding="utf-8")
            copied = project_routes._copy_project_tree_missing(source, target)
            self.assertEqual(copied, 1)
            self.assertEqual(project_routes._repo_rel_path(repo, str(source / "nested" / "a.txt")), "source/nested/a.txt")
            self.assertEqual(project_routes._clean_output_title("20260514_120001_my_report"), "my report")
            self.assertEqual(project_routes._normalize_promote_mode("clone"), "clone")
            self.assertEqual(project_routes._normalize_promote_mode("cutoff"), "move")

    def test_project_helpers_collect_outputs_and_clone_attachments(self) -> None:
        with tempfile.TemporaryDirectory(prefix="project_collect_") as tmp:
            repo = Path(tmp)
            summary = repo / "Projects" / "demo" / "implementation" / "note.md"
            summary.parent.mkdir(parents=True, exist_ok=True)
            summary.write_text("summary", encoding="utf-8")
            sidecar = summary.with_name("note_raw.md")
            sidecar.write_text("raw", encoding="utf-8")
            orch = SimpleNamespace(
                repo_root=repo,
                activity_store=_Rows(
                    [
                        {
                            "ts": "2026-05-14T00:00:00+00:00",
                            "event": "make_deliverable_written",
                            "details": {
                                "project": "demo",
                                "make_type": "essay_long",
                                "summary_path": str(summary),
                                "request_id": "req_7",
                                "topic": "Status report",
                            },
                        }
                    ]
                ),
            )
            rows = project_routes._collect_project_make_outputs(orch=orch, project="demo", limit=20)
            self.assertEqual(len(rows), 1)
            self.assertEqual(rows[0]["request_id"], "req_7")
            profile = {"id": "owner"}
            ctx = _FakeCtx(repo)
            src_conv = "conv_src"
            dst_conv = "conv_dst"
            src_dir = ctx.attachment_dir_for(profile, src_conv)
            (src_dir / "diagram.png").write_bytes(b"img")
            source_messages = [{"attachments": [{"filename": "diagram.png", "url": "/old"}]}]
            cloned, copied_files, missing_files = project_routes._clone_messages_with_attachments(
                ctx,
                profile,
                source_conversation_id=src_conv,
                target_conversation_id=dst_conv,
                source_messages=source_messages,
            )
            self.assertEqual(copied_files, 1)
            self.assertEqual(missing_files, 0)
            self.assertIn("/api/conversations/conv_dst/attachments/", cloned[0]["attachments"][0]["url"])

    def test_system_support_asset_versions_and_mime_guess(self) -> None:
        asset_v, vendor_v = support_routes.asset_versions()
        self.assertIsInstance(asset_v, int)
        self.assertIsInstance(vendor_v, int)
        self.assertEqual(support_routes.guess_mime_from_ext(".png"), "image/png")
        self.assertEqual(support_routes.guess_mime_from_ext(".unknown"), "application/octet-stream")


if __name__ == "__main__":
    unittest.main()
