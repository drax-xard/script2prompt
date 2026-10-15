"""Parser tests: plain-text heuristics and Fountain markers."""
from __future__ import annotations

import unittest

from script2prompt.parsers import fountain, plaintext


class TestPlaintext(unittest.TestCase):
    def test_full_block(self) -> None:
        text = (
            "INT. COFFEE SHOP - DAY\n"
            "\n"
            "Mara wipes the counter.\n"
            "\n"
            "MARA\n"
            "(softly)\n"
            "First batch of the morning.\n"
            "Still warm.\n"
            "\n"
            "CUT TO:\n"
        )
        kinds = [e.kind for e in plaintext.parse(text)]
        self.assertEqual(
            kinds,
            ["heading", "action", "character", "parenthetical", "dialogue", "dialogue", "transition"],
        )

    def test_cue_extension(self) -> None:
        el, _ = plaintext.parse("MARA (O.S.)\nHello?\n")
        self.assertEqual(el.kind, "character")
        self.assertEqual(el.meta["name"], "MARA")
        self.assertEqual(el.meta["extension"], "(O.S.)")

    def test_shouting_is_not_a_cue(self) -> None:
        elements = plaintext.parse("MARA\nGet out!\nLEO\nNow!\n")
        kinds = [e.kind for e in elements]
        self.assertEqual(kinds, ["character", "dialogue", "character", "dialogue"])

    def test_blank_line_ends_dialogue_block(self) -> None:
        elements = plaintext.parse("MARA\nHello.\n\nThe bell rings.\n")
        kinds = [e.kind for e in elements]
        self.assertEqual(kinds, ["character", "dialogue", "action"])


class TestFountain(unittest.TestCase):
    def test_forced_markers(self) -> None:
        text = ".OPENING CREDITS\n\n@mcconaughey\n> MATCH CUT TO:\n"
        elements = fountain.parse(text)
        self.assertEqual(
            [(e.kind, e.text) for e in elements],
            [("heading", "OPENING CREDITS"), ("character", "@mcconaughey"), ("transition", "MATCH CUT TO:")],
        )
        self.assertEqual(elements[1].meta["name"], "MCCONAUGHEY")

    def test_standard_headings_still_work(self) -> None:
        (el,) = fountain.parse("EXT. ROOFTOP - NIGHT\n")
        self.assertEqual((el.kind, el.text), ("heading", "EXT. ROOFTOP - NIGHT"))


if __name__ == "__main__":
    unittest.main()
