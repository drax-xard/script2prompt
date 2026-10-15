"""Keyframe mode tests: I2VA/FL2VA/L2VA build shapes and validation."""
from __future__ import annotations

import unittest

from script2prompt.core import chunker, h3_builder, scenes, validator
from script2prompt.core.characters import build_bible
from script2prompt.parsers import plaintext

TEXT = (
    "INT. COFFEE SHOP - DAY\n\n"
    "MARA (30s, tired barista) wipes the counter. Rain taps the windows.\n\n"
    "MARA\nFirst batch of the morning.\n\n"
    "The bell rings. LEO enters, shaking rain from his jacket.\n"
)


def build_all(mode: str):
    parsed = plaintext.parse(TEXT)
    found = scenes.split(parsed)
    bible = build_bible(found)
    chunks = [c for s in found for c in chunker.chunk(s, bible, mode=mode)]
    return bible, chunks


class TestKeyframeBuilds(unittest.TestCase):
    def test_i2va_anchors_picture_1(self) -> None:
        bible, chunks = build_all("I2VA")
        prompt = h3_builder.build(chunks[0], bible, mode="I2VA")
        lines = prompt.splitlines()
        self.assertEqual(
            lines[0],
            "For the target video, at 0.00 seconds into the target video, "
            "<Picture 1> (from [Shot 1]) is fully referenced.",
        )
        self.assertEqual(lines[1], "")
        self.assertIn("<Picture 1>", prompt)
        self.assertEqual(validator.validate(prompt, mode="I2VA", duration=chunks[0]["duration"]), [])

    def test_fl2va_single_shot_path(self) -> None:
        bible, chunks = build_all("FL2VA")
        self.assertTrue(chunks)
        for ch in chunks:
            self.assertEqual(len(ch["shots"]), 1)
            prompt = h3_builder.build(ch, bible, mode="FL2VA")
            self.assertIn("Picture 1 (from Shot 1) aligns with the 0.00-second mark", prompt)
            self.assertIn("Picture 2 (from Shot 1) aligns with", prompt)
            self.assertIn("established by Picture 2 at the end of the shot", prompt)
            self.assertEqual(validator.validate(prompt, mode="FL2VA", duration=ch["duration"]), [])

    def test_l2va_converges(self) -> None:
        bible, chunks = build_all("L2VA")
        prompt = h3_builder.build(chunks[0], bible, mode="L2VA")
        self.assertIn("aligns with", prompt.splitlines()[0])
        self.assertIn("<Picture 1>", prompt)
        self.assertIn("established by", prompt)
        self.assertEqual(validator.validate(prompt, mode="L2VA", duration=chunks[0]["duration"]), [])


class TestKeyframeValidation(unittest.TestCase):
    def test_missing_instruction_line(self) -> None:
        bible, chunks = build_all("I2VA")
        prompt = h3_builder.build(chunks[0], bible, mode="I2VA")
        stripped = "\n".join(prompt.splitlines()[2:])
        issues = validator.validate(stripped, mode="I2VA", duration=chunks[0]["duration"])
        self.assertTrue(any("instruction line" in i for i in issues))

    def test_fl2va_rejects_multi_shot(self) -> None:
        bible, chunks = build_all("T2VA")
        multi = next((c for c in chunks if len(c["shots"]) > 1), None)
        if multi is None:
            self.skipTest("sample yields a single multi-shot chunk; covered by builder")
        prompt = h3_builder.build(multi, bible, mode="FL2VA")
        issues = validator.validate(prompt, mode="FL2VA", duration=multi["duration"])
        self.assertTrue(any("single shot" in i for i in issues))

    def test_unknown_mode(self) -> None:
        self.assertTrue(validator.validate("x", mode="NOPE"))


if __name__ == "__main__":
    unittest.main()
