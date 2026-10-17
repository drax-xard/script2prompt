"""Parser tests: plain-text heuristics, Fountain markers, FDX, PDF, dispatch."""
from __future__ import annotations

import sys
import tempfile
import types
import unittest
from pathlib import Path
from unittest import mock

from script2prompt.parsers import fdx, fountain, parse_file, pdf, plaintext


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

    def test_slugline_inside_dialogue_is_dialogue(self) -> None:
        text = "MARA\nI went to the old house.\nINT. OLD HOUSE - NIGHT\nIt was empty.\n"
        elements = plaintext.parse(text)
        self.assertEqual(
            [(e.kind, e.text) for e in elements],
            [
                ("character", "MARA"),
                ("dialogue", "I went to the old house."),
                ("dialogue", "INT. OLD HOUSE - NIGHT"),
                ("dialogue", "It was empty."),
            ],
        )


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


FDX = """<?xml version="1.0" encoding="UTF-8" standalone="no"?>
<FinalDraft DocumentType="Script" Version="5">
  <Content>
    <Paragraph Type="Scene Heading"><Text>INT. COFFEE SHOP - DAY</Text></Paragraph>
    <Paragraph Type="Action"><Text>Mara wipes the </Text><Text Style="Italic">counter</Text><Text>. Rain taps the windows.</Text></Paragraph>
    <Paragraph Type="Character"><Text>MARA</Text></Paragraph>
    <Paragraph Type="Parenthetical"><Text>(softly)</Text></Paragraph>
    <Paragraph Type="Dialogue"><Text>First batch of the morning.</Text></Paragraph>
    <Paragraph Type="Transition"><Text>CUT TO:</Text></Paragraph>
  </Content>
</FinalDraft>
"""


class TestFdx(unittest.TestCase):
    def test_full_block(self) -> None:
        elements = fdx.parse_string(FDX)
        self.assertEqual(
            [e.kind for e in elements],
            ["heading", "action", "character", "parenthetical", "dialogue", "transition"],
        )
        self.assertEqual(
            elements[1].text, "Mara wipes the counter. Rain taps the windows."
        )
        self.assertEqual(elements[2].meta["name"], "MARA")

    def test_cue_extension(self) -> None:
        xml = '<FinalDraft><Content><Paragraph Type="Character"><Text>MARA (V.O.)</Text></Paragraph></Content></FinalDraft>'
        (el,) = fdx.parse_string(xml)
        self.assertEqual(el.meta["name"], "MARA")
        self.assertEqual(el.meta["extension"], "(V.O.)")

    def test_dual_dialogue_and_unknown_types(self) -> None:
        xml = (
            "<FinalDraft><Content>"
            '<Paragraph Type="Character"><Text>MARA</Text></Paragraph>'
            "<DualDialogue>"
            '<Paragraph Type="Character"><Text>LEO</Text></Paragraph>'
            '<Paragraph Type="Dialogue"><Text>Together.</Text></Paragraph>'
            "</DualDialogue>"
            '<Paragraph Type="Cast List"><Text>Ignored</Text></Paragraph>'
            '<Paragraph Type="Shot"><Text>Ignored</Text></Paragraph>'
            "</Content></FinalDraft>"
        )
        elements = fdx.parse_string(xml)
        self.assertEqual([e.kind for e in elements], ["character", "character", "dialogue"])
        self.assertEqual([e.text for e in elements], ["MARA", "LEO", "Together."])

    def test_title_page_ignored(self) -> None:
        xml = (
            "<FinalDraft>"
            '<TitlePage><Content><Paragraph Type="Action"><Text>MY SCRIPT</Text></Paragraph></Content></TitlePage>'
            '<Content><Paragraph Type="Action"><Text>Real action.</Text></Paragraph></Content>'
            "</FinalDraft>"
        )
        (el,) = fdx.parse_string(xml)
        self.assertEqual(el.text, "Real action.")

    def test_parse_from_file(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "s.fdx"
            path.write_text(FDX, encoding="utf-8")
            self.assertEqual([e.kind for e in fdx.parse(str(path))][0], "heading")


class _FakePage:
    def __init__(self, text: str) -> None:
        self._text = text

    def extract_text(self) -> str:
        return self._text


class _FakeReader:
    def __init__(self, path: str) -> None:
        self.pages = [_FakePage("INT. ROOM - DAY\n\nMARA\nHi there.\n")]


class TestPdf(unittest.TestCase):
    def test_missing_extra_message(self) -> None:
        with mock.patch.dict(sys.modules, {"pypdf": None}), self.assertRaises(ImportError) as ctx:
            pdf.extract_text("whatever.pdf")
        self.assertIn("pip install .[pdf]", str(ctx.exception))

    def test_extract_and_parse_with_fake_pypdf(self) -> None:
        fake = types.SimpleNamespace(PdfReader=_FakeReader)
        with mock.patch.dict(sys.modules, {"pypdf": fake}):
            self.assertIn("MARA", pdf.extract_text("x.pdf"))
            elements = pdf.parse("x.pdf")
        self.assertEqual([e.kind for e in elements], ["heading", "character", "dialogue"])
        self.assertEqual(elements[1].meta["name"], "MARA")


class TestDispatch(unittest.TestCase):
    def _write(self, tmp: str, name: str, text: str) -> str:
        path = Path(tmp) / name
        path.write_text(text, encoding="utf-8")
        return str(path)

    def test_picks_parser_by_suffix(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            txt = self._write(tmp, "a.txt", "INT. A - DAY\n\nMARA\nHi.\n")
            fou = self._write(tmp, "b.fountain", "@MARA\n> CUT TO:\n")
            fdx_path = self._write(tmp, "c.fdx", FDX)
            unknown = self._write(tmp, "d.screenplay", "INT. B - DAY\n\nLEO\nYo.\n")

            self.assertEqual(parse_file(txt)[0].kind, "heading")
            self.assertEqual([e.kind for e in parse_file(fou)], ["character", "transition"])
            self.assertEqual(parse_file(fdx_path)[0].kind, "heading")
            self.assertEqual(parse_file(unknown)[0].kind, "heading")


if __name__ == "__main__":
    unittest.main()
