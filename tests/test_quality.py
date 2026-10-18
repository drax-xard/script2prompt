"""Tests for the 0.10.0 output-quality fixes (action splitting, tiny chunks,
name casing, environment naming)."""
from __future__ import annotations

import os
import re
import unittest
from unittest import mock

from script2prompt.core import chunker, config, ref_manifest, scenes
from script2prompt.core.characters import build_bible, title
from script2prompt.core.h3_builder import build
from script2prompt.parsers import plaintext
from script2prompt.parsers.base import Element


def words(n: int) -> str:
    return " ".join(f"w{i}" for i in range(n))


def action_scene(*texts: str) -> dict:
    return {
        "context": "INT. R - DAY",
        "elements": [Element("action", t) for t in texts],
    }


class TestActionSplit(unittest.TestCase):
    def test_long_action_is_split_into_pieces(self) -> None:
        pieces = chunker._split_long_action([Element("action", words(80))])
        self.assertGreater(len(pieces), 1)
        for piece in pieces:
            self.assertLessEqual(chunker.count_words(piece.text), chunker.ACTION_PIECE_WORDS)

    def test_short_action_is_untouched(self) -> None:
        el = Element("action", words(10))
        self.assertEqual(chunker._split_long_action([el]), [el])

    def test_long_action_respects_cap(self) -> None:
        chunks = chunker.chunk(action_scene(words(120)))
        for ch in chunks:
            self.assertLessEqual(chunker.estimate(ch["elements"]), chunker.CAP_SECONDS + 1e-9)


class TestTinyChunkMerge(unittest.TestCase):
    def test_tiny_tail_merges_into_predecessor(self) -> None:
        # 30-word beat (5.8s) then a 4-word tail: without merging the tail would
        # become its own 5s chunk, doubling runtime for one line.
        chunks = chunker.chunk(action_scene(words(30), "A short beat."), duration=5.0)
        self.assertEqual(len(chunks), 1)
        self.assertLess(chunks[0]["duration"], chunker.CAP_SECONDS)

    def test_merge_never_exceeds_cap(self) -> None:
        # Predecessor is already ~10s, so the tiny tail cannot join it and must
        # stand alone (floored to the 5s minimum).
        chunks = chunker.chunk(action_scene(words(56), "A short beat."), duration=8.0)
        self.assertEqual(len(chunks), 2)
        self.assertEqual(chunks[-1]["duration"], chunker.MIN_SECONDS)

    def test_sole_tiny_chunk_is_floored(self) -> None:
        chunks = chunker.chunk(action_scene("A short beat."))
        self.assertEqual(len(chunks), 1)
        self.assertEqual(chunks[0]["duration"], chunker.MIN_SECONDS)


class TestTitleCasing(unittest.TestCase):
    def test_hyphen_and_apostrophe_preserved(self) -> None:
        self.assertEqual(title("MARY-JANE"), "Mary-Jane")
        self.assertEqual(title("O'BRIEN"), "O'Brien")
        self.assertEqual(title("MARY JANE"), "Mary Jane")
        self.assertEqual(title("WILL'S DATE"), "Will's Date")
        self.assertEqual(title("JAMES'S"), "James's")

    def test_alphanumeric_designator_preserved(self) -> None:
        self.assertEqual(title("C3PO"), "C3PO")
        self.assertEqual(title("R2D2"), "R2D2")
        self.assertEqual(title("AGENT 47"), "Agent 47")

    def test_caps_apostrophe_name_is_detected(self) -> None:
        text = "INT. BAR - NIGHT\n\nO'BRIEN\nLast call.\n"
        names = {c.name for c in build_bible(scenes.split(plaintext.parse(text)))}
        self.assertIn("O'BRIEN", names)

    def test_single_letter_mentions_ignored(self) -> None:
        # Bare "I" in action text must not become a recurring silent character.
        names = {c.name for c in build_bible(scenes.split(plaintext.parse("I wait.\nI wait.\n")))}
        self.assertNotIn("I", names)


class TestEnvironmentNaming(unittest.TestCase):
    def test_slugline_parts(self) -> None:
        self.assertEqual(ref_manifest.slugline_parts("INT. NEWSROOM - NIGHT"), ("Newsroom", "Night"))
        self.assertEqual(ref_manifest.slugline_parts("EXT. OPEN-PLAN OFFICE - DAY"),
                         ("Open-Plan Office", "Day"))
        self.assertEqual(ref_manifest.slugline_parts("EST. CITY SKYLINE"), ("City Skyline", ""))

    def test_subject_uses_location_not_raw_slugline(self) -> None:
        text = "INT. NEWSROOM - NIGHT\n\nMARA\nPrint it.\n"
        found = scenes.split(plaintext.parse(text))
        bible = build_bible(found)
        chunk = chunker.chunk(found[0], bible)[0]
        subject = ref_manifest.propose(chunk, bible)["subjects"][0]
        self.assertEqual(subject["name"], "Newsroom")
        self.assertEqual(subject["description"], "Night")

    def test_r2v_definitions_use_location_and_time(self) -> None:
        text = "INT. NEWSROOM - NIGHT\n\nMARA\nPrint it.\n"
        found = scenes.split(plaintext.parse(text))
        bible = build_bible(found)
        chunk = chunker.chunk(found[0], bible)[0]
        prompt = build(chunk, bible, mode="R2V")
        self.assertIn("the Newsroom environment at night", prompt)
        self.assertNotIn("INT. NEWSROOM", prompt)


NEWSROOM = (
    "INT. NEWSROOM - NIGHT\n\n"
    "A bank of monitors flickers. The elevator dings behind the desks.\n\n"
    "ELENA (40s, sharp editor) presses a phone to her ear.\n\n"
    "ELENA\nPrint it. I don't care who it burns.\n\n"
    "DANI, a nervous junior reporter, clutches a notepad.\n\n"
    "DANI\nThey'll fire you for this.\n\n"
)


class TestGeneratedPromptQuality(unittest.TestCase):
    """The deterministic templates must read like the H3 example prompts."""

    def setUp(self) -> None:
        found = scenes.split(plaintext.parse(NEWSROOM))
        self.bible = build_bible(found)
        self.chunks = [c for s in found for c in chunker.chunk(s, self.bible)]

    def _prompt(self, i: int) -> str:
        return build(self.chunks[i], self.bible)

    def test_no_raw_slugline(self) -> None:
        for chunk in self.chunks:
            self.assertNotIn("INT. NEWSROOM", build(chunk, self.bible))

    def test_first_shot_has_no_timestamp(self) -> None:
        for chunk in self.chunks:
            shot1 = build(chunk, self.bible).split("[Shot 1]", 1)[1].split("[Shot 2]", 1)[0]
            self.assertNotIn("At 00:", shot1)

    def test_camera_motion_varies_within_chunk(self) -> None:
        cams = re.findall(r"The camera (\w+)", self._prompt(0))
        self.assertGreaterEqual(len(cams), 2)
        self.assertEqual(len(cams), len(set(cams)))

    def test_soundscape_excludes_dialogue_and_names(self) -> None:
        for chunk in self.chunks:
            sound = (build(chunk, self.bible)
                     .split("overall_soundscape:\n", 1)[1]
                     .split("\n\nnon_diegetic_music:", 1)[0])
            self.assertNotIn("<d>", sound)
            self.assertNotIn("(S", sound)
            self.assertNotIn("Elena", sound)
            self.assertNotIn("Dani", sound)

    def test_dialogue_sits_inside_description(self) -> None:
        for chunk in self.chunks:
            prompt = build(chunk, self.bible)
            if "<d>" in prompt:
                self.assertLess(prompt.index("<d>"), prompt.index("overall_soundscape:"))

    def test_music_defaults_to_na(self) -> None:
        for chunk in self.chunks:
            self.assertIn("non_diegetic_music:\nN/A", build(chunk, self.bible))

    def test_music_written_when_script_names_score(self) -> None:
        text = "INT. BAR - NIGHT\n\nA slow score plays.\n\nMARA\nLast call.\n"
        found = scenes.split(plaintext.parse(text))
        bible = build_bible(found)
        chunk = chunker.chunk(found[0], bible)[0]
        self.assertNotIn("non_diegetic_music:\nN/A", build(chunk, bible))

    def test_appositive_description_is_captured(self) -> None:
        descs = {c.name: c.description for c in self.bible}
        self.assertEqual(descs.get("DANI"), "nervous junior reporter")


class TestConfigEnv(unittest.TestCase):
    def test_temperature_and_timeout_env_overrides(self) -> None:
        env = {"S2P_TEMPERATURE": "0.9", "S2P_TIMEOUT": "30"}
        with mock.patch.dict(os.environ, env):
            loaded = config.load("nonexistent.toml", "nonexistent-local.toml")
        self.assertEqual(loaded["llm"]["temperature"], 0.9)
        self.assertEqual(loaded["llm"]["timeout"], 30)

    def test_llm_defaults(self) -> None:
        with mock.patch.dict(os.environ, {}, clear=True):
            loaded = config.load("nonexistent.toml", "nonexistent-local.toml")
        self.assertEqual(loaded["llm"]["max_tokens"], 2048)
        self.assertEqual(loaded["llm"]["timeout"], 120)
        self.assertEqual(loaded["llm"]["retries"], 2)


if __name__ == "__main__":
    unittest.main()
