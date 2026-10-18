"""Community dialogue delivery tags: parenthetical mapping and rendering."""
from __future__ import annotations

import unittest

from script2prompt.core import chunker, delivery, scenes, validator
from script2prompt.core.characters import build_bible
from script2prompt.core.h3_builder import build
from script2prompt.parsers import plaintext


class TestTagTable(unittest.TestCase):
    def test_wrap_tags_have_closing_form(self) -> None:
        for entry in delivery.DELIVERY_TAGS:
            tag = str(entry["tag"])
            self.assertTrue(tag.startswith("<") and tag.endswith(">"))
            if entry["wrap"]:
                self.assertIn(tag, delivery.WRAP_TAGS)

    def test_all_tags_are_the_reference_set(self) -> None:
        self.assertEqual(len(delivery.ALL_TAGS), 22)
        self.assertEqual(len(set(delivery.ALL_TAGS)), 22)


class TestTagFor(unittest.TestCase):
    def test_exact_matches(self) -> None:
        self.assertEqual(delivery.tag_for("beat"), ("<pause>", False))
        self.assertEqual(delivery.tag_for("whispering"), ("<whisper>", True))
        self.assertEqual(delivery.tag_for("sighs"), ("<sighs>", False))
        self.assertEqual(delivery.tag_for("clears throat"), ("<clears throat>", False))

    def test_containment_prefers_longest_phrase(self) -> None:
        self.assertEqual(delivery.tag_for("a long pause"), ("<long pause>", False))
        self.assertEqual(delivery.tag_for("under breath"), ("<softer>", False))

    def test_non_delivery_parentheticals_are_ignored(self) -> None:
        for text in ("V.O.", "CONT'D", "O.S.", "to Will", "closer",
                     "low but insistent", ""):
            self.assertIsNone(delivery.tag_for(text), text)

    def test_wrapped_tag_closing_preserved(self) -> None:
        self.assertEqual(delivery.apply_tags("Don't move.", "whispering"),
                         "<whisper>Don't move.</whisper>")

    def test_leading_tag_prefixed(self) -> None:
        self.assertEqual(delivery.apply_tags("Fine.", "softly"), "<softer> Fine.")


class TestDeterministicTagging(unittest.TestCase):
    SCRIPT = (
        "INT. LAB - NIGHT\n\n"
        "MARA\n(whispering)\nDon't move.\n\n"
        "LEO\n(beat)\nOkay, okay.\n\n"
        "MARA\n(sighs)\nFine. Have it your way.\n\n"
        "LEO\n(to Mara)\nI mean it.\n"
    )

    def setUp(self) -> None:
        found = scenes.split(plaintext.parse(self.SCRIPT))
        self.bible = build_bible(found)
        self.chunks = [c for s in found for c in chunker.chunk(s, self.bible)]

    def test_cued_deliveries_become_tags(self) -> None:
        prompt = "\n".join(build(c, self.bible) for c in self.chunks)
        self.assertIn("<d>[English]<whisper>Don't move.</whisper></d>", prompt)
        self.assertIn("<d>[English]<pause> Okay, okay.</d>", prompt)
        self.assertIn("<d>[English]<sighs> Fine. Have it your way.</d>", prompt)

    def test_ambiguous_parenthetical_adds_no_tag(self) -> None:
        prompt = "\n".join(build(c, self.bible) for c in self.chunks)
        self.assertIn("<d>[English]I mean it.</d>", prompt)

    def test_tagged_prompts_validate(self) -> None:
        for chunk in self.chunks:
            self.assertEqual(
                validator.validate(build(chunk, self.bible),
                                   duration=chunk["duration"], bible=self.bible),
                [],
            )


if __name__ == "__main__":
    unittest.main()
