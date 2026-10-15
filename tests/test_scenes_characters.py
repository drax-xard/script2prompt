"""Scene splitter and character bible tests."""
from __future__ import annotations

import unittest

from script2prompt.core import scenes
from script2prompt.core.characters import build_bible
from script2prompt.parsers import plaintext

TWO_SCENES = (
    "INT. COFFEE SHOP - DAY\n\nMara wipes the counter.\n\n"
    "EXT. STREET - NIGHT\n\nLEO\nHello?\n"
)


class TestScenes(unittest.TestCase):
    def test_split_keeps_context(self) -> None:
        result = scenes.split(plaintext.parse(TWO_SCENES))
        self.assertEqual(len(result), 2)
        self.assertEqual(result[0]["heading"], "INT. COFFEE SHOP - DAY")
        self.assertEqual(result[0]["context"], "INT. COFFEE SHOP - DAY")
        self.assertEqual(result[1]["heading"], "EXT. STREET - NIGHT")

    def test_cold_open(self) -> None:
        (scene,) = scenes.split(plaintext.parse("Mara wakes up.\n"))
        self.assertEqual(scene["heading"], "")
        self.assertEqual(len(scene["elements"]), 1)


class TestBible(unittest.TestCase):
    def test_speaker_order_and_traits(self) -> None:
        text = (
            "INT. SHOP - DAY\n\n"
            "MARA (30s, tired barista) wipes the counter.\n\n"
            "MARA\nHello.\n\n"
            "LEO enters.\n\n"
            "LEO\nHi.\n"
        )
        bible = build_bible(scenes.split(plaintext.parse(text)))
        by_name = {c.name: c for c in bible}
        self.assertEqual(by_name["MARA"].speaker_id, "S1")
        self.assertEqual(by_name["MARA"].description, "30s, tired barista")
        self.assertEqual(by_name["LEO"].speaker_id, "S2")

    def test_nonvocal_gets_no_id(self) -> None:
        text = "INT. SHOP - DAY\n\nLEO enters, shaking rain off.\n\nMARA\nHi.\n"
        by_name = {c.name: c for c in build_bible(scenes.split(plaintext.parse(text)))}
        self.assertIsNone(by_name["LEO"].speaker_id)
        self.assertEqual(by_name["MARA"].speaker_id, "S1")


if __name__ == "__main__":
    unittest.main()
