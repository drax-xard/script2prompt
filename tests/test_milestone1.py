"""Chunker, T2VA builder, validator, and end-to-end tests."""
from __future__ import annotations

import re
import unittest
from pathlib import Path

from script2prompt.core import chunker, h3_builder, scenes, validator
from script2prompt.core.characters import build_bible
from script2prompt.core.modes import instruction_line
from script2prompt.parsers import plaintext


def pipeline(text: str, **kwargs):
    parsed = plaintext.parse(text)
    found = scenes.split(parsed)
    bible = build_bible(found)
    chunks = [c for s in found for c in chunker.chunk(s, bible, **kwargs)]
    return bible, chunks


class TestChunker(unittest.TestCase):
    def test_caps_and_shots(self) -> None:
        text = (
            "INT. SHOP - DAY\n\nAction line one two three four five.\n\n"
            "MARA\nHello there friend.\n\nLEO\nHi back to you.\n"
        )
        _, chunks = pipeline(text)
        for ch in chunks:
            self.assertLessEqual(ch["duration"], 10.0)
            self.assertGreaterEqual(ch["duration"], 5.0)
            self.assertLessEqual(len(ch["shots"]), 3)
        stamps = [s["start"] for ch in chunks for s in ch["shots"]]
        self.assertTrue(all(re.fullmatch(r"\d{2}:\d{2}\.\d{3}", s) for s in stamps))

    def test_monologue_splits_with_markers(self) -> None:
        words = " ".join(f"word{i}" for i in range(60))
        text = f"INT. ROOM - DAY\n\nMARA\n{words}.\n"
        _, chunks = pipeline(text)
        self.assertGreater(len(chunks), 1)
        marks = [e.meta.get("scenetrans", "") for c in chunks for e in c["elements"]]
        self.assertIn("out", marks)
        self.assertIn("in", marks)

    def test_timestamps_increase_inside_duration(self) -> None:
        text = "INT. A - DAY\n\nMARA\nOne two three.\n\nLEO\nFour five six.\n"
        _, chunks = pipeline(text)
        for ch in chunks:
            times = [s["start"] for s in ch["shots"]]
            self.assertEqual(times, sorted(times))
            last = times[-1].split(":")
            self.assertLess(float(last[0]) * 60 + float(last[1]), ch["duration"])


class TestModes(unittest.TestCase):
    def test_t2va_has_no_instruction(self) -> None:
        self.assertEqual(instruction_line("T2VA"), "")

    def test_keyframe_lines(self) -> None:
        self.assertIn("<Picture 1> (from [Shot 1])", instruction_line("I2VA"))
        fl = instruction_line("FL2VA", final_shot=2, duration=8.0)
        self.assertIn("Picture 2 (from Shot 2)", fl)
        self.assertIn("8.00-second", fl)
        lv = instruction_line("L2VA", final_shot=3, duration=6.0)
        self.assertIn("[Shot 3]", lv)
        self.assertIn("6.00-second", lv)

    def test_unknown_mode(self) -> None:
        with self.assertRaises(ValueError):
            instruction_line("NOPE")


class TestT2VA(unittest.TestCase):
    def test_build_validates_clean(self) -> None:
        text = (
            "INT. COFFEE SHOP - DAY\n\n"
            "MARA (30s, tired barista) wipes the counter. Rain taps the windows.\n\n"
            "MARA\nFirst batch of the morning.\n"
        )
        bible, chunks = pipeline(text)
        self.assertEqual(len(chunks), 1)
        prompt = h3_builder.build(chunks[0], bible)
        self.assertEqual(validator.validate(prompt, duration=chunks[0]["duration"]), [])
        # Example-prompt layout: labels on their own lines, style sentence first.
        self.assertTrue(prompt.startswith("integrated_multimodal_description:\nLive-action, cinematic.\n[Shot 1]"))
        self.assertIn("Mara, 30s, tired barista (S1) says <d>[English]First batch of the morning.</d>.", prompt)
        self.assertIn("overall_soundscape:\n", prompt)
        self.assertTrue(prompt.rstrip().endswith("non_diegetic_music:\nN/A"))

    def test_voiceover(self) -> None:
        text = "INT. ROOM - NIGHT\n\nMARA (V.O.)\nI still remember that road.\n"
        bible, chunks = pipeline(text)
        prompt = h3_builder.build(chunks[0], bible)
        self.assertIn("says in an off-screen voiceover:", prompt)
        self.assertIn("lips remain completely closed", prompt)
        self.assertEqual(validator.validate(prompt, duration=chunks[0]["duration"]), [])

    def test_validator_catches_bad_shots(self) -> None:
        bad = (
            "integrated_multimodal_description: [Shot 1] At 00:01.000, x.\n\n"
            "overall_soundscape: Room tone.\n\nnon_diegetic_music: N/A"
        )
        issues = validator.validate(bad)
        self.assertTrue(any("must not have a timestamp" in i for i in issues))


class TestEndToEnd(unittest.TestCase):
    def test_sample_scene(self) -> None:
        text = Path("samples/sample_scene.txt").read_text()
        bible, chunks = pipeline(text)
        names = {c.name: c.speaker_id for c in bible}
        self.assertEqual(names.get("MARA"), "S1")
        self.assertTrue(chunks)
        for ch in chunks:
            prompt = h3_builder.build(ch, bible)
            self.assertEqual(validator.validate(prompt, duration=ch["duration"]), [])


if __name__ == "__main__":
    unittest.main()
