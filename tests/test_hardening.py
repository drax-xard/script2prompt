"""Regression tests for the deep-audit bug fixes (see IMPROVEMENTS.md)."""
from __future__ import annotations

import json
import tempfile
import unittest
from contextlib import redirect_stdout
from io import StringIO
from pathlib import Path
from unittest import mock

from script2prompt import __main__ as cli
from script2prompt.core import chunker, config, h3_builder, scenes, validator
from script2prompt.core.characters import Character, build_bible
from script2prompt.parsers import fountain, parse_file, plaintext
from script2prompt.parsers.base import Element


def pipeline(text: str, **kwargs):
    found = scenes.split(plaintext.parse(text))
    bible = build_bible(found)
    chunks = [c for s in found for c in chunker.chunk(s, bible, **kwargs)]
    return bible, chunks


class TestChunkerCueIntegrity(unittest.TestCase):
    def test_cue_never_split_from_dialogue(self) -> None:
        # 24 words: fits the cap but would previously flush the cue alone.
        words = " ".join(f"w{i}" for i in range(24))
        bible, chunks = pipeline(f"INT. R - DAY\n\nMARA\n{words}.\n")
        for ch in chunks:
            self.assertTrue(any(e.kind == "character" for e in ch["elements"]))
            self.assertNotEqual([e.kind for e in ch["elements"]], ["character"])
            prompt = h3_builder.build(ch, bible)
            self.assertNotIn("unseen speaker", prompt.lower())
            self.assertIn("(S1)", prompt)

    def test_monologue_continuation_keeps_speaker(self) -> None:
        words = " ".join(f"w{i}" for i in range(60))
        bible, chunks = pipeline(f"INT. R - DAY\n\nMARA\n{words}.\n")
        self.assertGreater(len(chunks), 1)
        for ch in chunks:
            prompt = h3_builder.build(ch, bible)
            self.assertNotIn("unseen speaker", prompt.lower())
            self.assertIn("(S1)", prompt)


class TestChunkerBudget(unittest.TestCase):
    def test_26_word_line_is_split_to_fit(self) -> None:
        words = " ".join(f"w{i}" for i in range(26))
        _, chunks = pipeline(f"INT. R - DAY\n\nMARA\n{words}.\n")
        for ch in chunks:
            self.assertLessEqual(chunker.estimate(ch["elements"]), chunker.CAP_SECONDS + 1e-9)

    def test_multiline_monologue_respects_cap(self) -> None:
        # Many short lines under one cue sum well past the cap; each chunk must
        # still fit and keep its speaker cue (no "unseen speaker").
        lines = "\n".join(f"line {i} carries several more words here" for i in range(8))
        _, chunks = pipeline(f"INT. R - DAY\n\nMARA\n{lines}\n")
        self.assertGreater(len(chunks), 1)
        for ch in chunks:
            self.assertLessEqual(chunker.estimate(ch["elements"]), chunker.CAP_SECONDS + 1e-9)
            self.assertEqual(ch["elements"][0].kind, "character")

    def test_parenthetical_interrupted_monologue_respects_cap(self) -> None:
        first = " ".join(f"a{i}" for i in range(15))
        second = " ".join(f"b{i}" for i in range(17))
        _, chunks = pipeline(f"INT. R - DAY\n\nWILL\n{first}\n(closer)\n{second}\n")
        for ch in chunks:
            self.assertLessEqual(chunker.estimate(ch["elements"]), chunker.CAP_SECONDS + 1e-9)

    def test_no_chunk_exceeds_cap_after_splitting(self) -> None:
        scene = {
            "context": "INT. R - DAY",
            "elements": [
                Element("character", "MARA"),
                *[Element("dialogue", f"piece {i} of a long speech continues") for i in range(10)],
            ],
        }
        for ch in chunker.chunk(scene):
            self.assertLessEqual(chunker.estimate(ch["elements"]), chunker.CAP_SECONDS + 1e-9)


class TestVoiceover(unittest.TestCase):
    def test_voiceover_with_delivery(self) -> None:
        _, chunks = pipeline("INT. R - NIGHT\n\nMARA (V.O.)\n(softly)\nI still remember.\n")
        prompt = h3_builder.build(chunks[0])
        self.assertIn("says in an off-screen voiceover:", prompt)
        self.assertIn("lips remain completely closed", prompt)

    def test_voiceover_with_extra_parenthetical(self) -> None:
        # (V.O.) followed by another marker must still read as a voiceover.
        _, chunks = pipeline("INT. R - NIGHT\n\nMARA (V.O.) (CONT'D)\nI still remember.\n")
        prompt = h3_builder.build(chunks[0])
        self.assertIn("off-screen voiceover", prompt)
        self.assertIn("lips remain completely closed", prompt)

    def test_off_screen_is_not_voiceover(self) -> None:
        _, chunks = pipeline("INT. R - NIGHT\n\nMARA (O.S.)\nI still remember.\n")
        prompt = h3_builder.build(chunks[0])
        self.assertNotIn("off-screen voiceover", prompt)
        self.assertNotIn("lips remain completely closed", prompt)


class TestParserHeuristics(unittest.TestCase):
    def test_dialogue_starting_with_ext_is_not_heading(self) -> None:
        els = plaintext.parse("MARA\nThe murder was at EXT. That's where I left it.\n")
        self.assertEqual([e.kind for e in els], ["character", "dialogue"])

    def test_lone_caps_beat_is_action(self) -> None:
        els = plaintext.parse("THUNDER\n\nMARA\nWhat was that?\n")
        self.assertEqual([e.kind for e in els], ["action", "character", "dialogue"])

    def test_fade_transitions(self) -> None:
        for line in ("FADE IN:", "FADE OUT.", "FADE TO BLACK."):
            (el,) = plaintext.parse(line + "\n")
            self.assertEqual(el.kind, "transition", line)

    def test_est_heading(self) -> None:
        (el,) = plaintext.parse("EST. CITY SKYLINE - DUSK\n")
        self.assertEqual(el.kind, "heading")

    def test_fountain_cue_lookahead(self) -> None:
        els = fountain.parse("@MARA\nHi.\n")
        self.assertEqual([e.kind for e in els], ["character", "dialogue"])


class TestTraits(unittest.TestCase):
    def test_midline_traits_captured(self) -> None:
        text = (
            "INT. N - NIGHT\n\nFluorescent lights hum. ELENA (40s, sharp editor) stands. "
            "Across the room a junior reporter, DANI (20s, nervous), clutches a notepad.\n"
        )
        by_name = {c.name: c.description for c in build_bible(scenes.split(plaintext.parse(text)))}
        self.assertEqual(by_name["ELENA"], "40s, sharp editor")
        self.assertEqual(by_name["DANI"], "20s, nervous")

    def test_joint_action_intro_is_split(self) -> None:
        text = "INT. R - NIGHT\n\nMARA AND LEO (30s, siblings) enter together.\n\nMARA\nHi.\n"
        by_name = {c.name: (c.speaker_id, c.description) for c in build_bible(scenes.split(plaintext.parse(text)))}
        self.assertNotIn("MARA AND LEO", by_name)
        # Both share the intro traits; only the speaker earns an ID.
        self.assertEqual(by_name["MARA"], ("S1", "30s, siblings"))
        self.assertEqual(by_name["LEO"], (None, "30s, siblings"))

    def test_caps_mention_does_not_swallow_connector(self) -> None:
        text = "INT. R - NIGHT\n\nThe ELENA AND MARA team regroups. ELENA speaks.\nELENA speaks.\n"
        names = {c.name for c in build_bible(scenes.split(plaintext.parse(text)))}
        self.assertNotIn("ELENA AND", names)
        self.assertNotIn("AND", names)
        self.assertIn("ELENA", names)

    def test_prop_parenthetical_is_not_a_character(self) -> None:
        text = "INT. N - NIGHT\n\nTHE SIGN (unreadable) glows.\n\nMARA\nHi.\n"
        names = {c.name for c in build_bible(scenes.split(plaintext.parse(text)))}
        self.assertNotIn("THE SIGN", names)


class TestValidatorSpeakers(unittest.TestCase):
    def test_unseen_speaker_flagged(self) -> None:
        bad = (
            "integrated_multimodal_description:\nLive-action, cinematic.\n[Shot 1] A room. "
            "An unseen speaker says <d>[English]Hi.</d>.\n\n"
            "overall_soundscape:\nRoom tone.\n\nnon_diegetic_music:\nN/A"
        )
        self.assertTrue(any("unseen speaker" in i for i in validator.validate(bad)))

    def test_unknown_speaker_id_flagged(self) -> None:
        bad = (
            "integrated_multimodal_description:\nLive-action, cinematic.\n[Shot 1] A room. "
            "Mara (S9) says <d>[English]Hi.</d>.\n\n"
            "overall_soundscape:\nRoom tone.\n\nnon_diegetic_music:\nN/A"
        )
        bible = [Character("MARA", "S1", "")]
        self.assertTrue(any("S9" in i for i in validator.validate(bad, bible=bible)))

    def test_valid_speaker_id_passes(self) -> None:
        good = (
            "integrated_multimodal_description:\nLive-action, cinematic.\n[Shot 1] A room. "
            "Mara (S1) says <d>[English]Hi.</d>.\n\n"
            "overall_soundscape:\nRoom tone.\n\nnon_diegetic_music:\nN/A"
        )
        bible = [Character("MARA", "S1", "")]
        self.assertEqual(validator.validate(good, bible=bible), [])


class TestJointSpeakers(unittest.TestCase):
    def test_compound_id_and_separate_bible_entries(self) -> None:
        text = (
            "INT. R - DAY\n\n"
            "MARA\nHello.\n\n"
            "LEO\nHi.\n\n"
            "MARA AND LEO\nTogether then.\n"
        )
        bible, chunks = pipeline(text)
        ids = {c.name: c.speaker_id for c in bible}
        self.assertEqual(ids, {"MARA": "S1", "LEO": "S2"})
        prompt = h3_builder.build(chunks[0], bible)
        self.assertIn("Mara and Leo (S1,S2) say <d>[English]Together then.</d>.", prompt)
        self.assertNotIn("unseen speaker", prompt.lower())

    def test_joint_first_appearance_assigns_ids(self) -> None:
        bible, chunks = pipeline("INT. R - DAY\n\nELENA & MARA\nWe agree.\n")
        self.assertEqual({c.name: c.speaker_id for c in bible}, {"ELENA": "S1", "MARA": "S2"})
        self.assertIn("Elena and Mara (S1,S2) say", h3_builder.build(chunks[0], bible))

    def test_and_inside_name_not_split(self) -> None:
        from script2prompt.core.characters import split_joint

        self.assertEqual(split_joint("ALEXANDER"), [])
        self.assertEqual(split_joint("SANDRA"), [])
        self.assertEqual(split_joint("AT&T"), [])
        self.assertEqual(split_joint("ELENA AND MARA"), ["ELENA", "MARA"])

    def test_validator_checks_every_compound_id(self) -> None:
        prompt = (
            "integrated_multimodal_description:\nLive-action, cinematic.\n"
            "[Shot 1] A room. Mara and Leo (S1,S9) say <d>[English]Hi.</d>.\n\n"
            "overall_soundscape:\nRoom tone.\n\nnon_diegetic_music:\nN/A"
        )
        bible = [Character("MARA", "S1", ""), Character("LEO", "S2", "")]
        issues = validator.validate(prompt, bible=bible)
        self.assertTrue(any("S9" in issue for issue in issues), issues)


class TestBuildGuard(unittest.TestCase):
    def test_scene_input_raises(self) -> None:
        with self.assertRaises(ValueError):
            h3_builder.build({"elements": [], "context": "INT. X - DAY"})


class TestConfigErrors(unittest.TestCase):
    def test_invalid_toml_is_friendly(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            bad = Path(tmp) / "bad.toml"
            bad.write_text("this is = = broken\n", encoding="utf-8")
            with self.assertRaises(ValueError) as ctx:
                config.load(bad, Path(tmp) / "missing.toml")
            self.assertIn("bad.toml", str(ctx.exception))

    def test_invalid_env_number_is_friendly(self) -> None:
        with mock.patch.dict("os.environ", {"S2P_TEMPERATURE": "hot"}), self.assertRaises(ValueError) as ctx:
            config.load(Path("/missing.toml"), Path("/missing.toml"))
        self.assertIn("S2P_TEMPERATURE", str(ctx.exception))


class TestBinaryRejected(unittest.TestCase):
    def test_binary_file_raises(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "s.txt"
            path.write_bytes(b"\x00\x01\x02INT. X - DAY")
            with self.assertRaises(ValueError):
                parse_file(path)


class TestCliDurationZero(unittest.TestCase):
    def test_zero_duration_override_is_used(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            with redirect_stdout(StringIO()):
                rc = cli.main(["samples/one_page.txt", "-o", tmp, "--duration", "0"])
            self.assertEqual(rc, 0)
            manifest = json.loads((Path(tmp) / "manifest.json").read_text(encoding="utf-8"))
            # 0 is honored (not silently replaced by the config default of 8.0),
            # then clamped up to the 5s minimum.
            self.assertEqual(manifest["duration_target"], 5.0)


if __name__ == "__main__":
    unittest.main()
