"""End-to-end pipeline, export pack, and CLI tests (Milestone 6)."""
from __future__ import annotations

import io
import json
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path

from script2prompt import __main__ as cli
from script2prompt.core import pipeline
from script2prompt.parsers import parse_file

SAMPLE = Path("samples/one_page.txt")
MODES = ("T2VA", "I2VA", "FL2VA", "L2VA", "R2V")


class TestRun(unittest.TestCase):
    def test_all_modes_validate_clean(self) -> None:
        elements = parse_file(str(SAMPLE))
        for mode in MODES:
            project = pipeline.run(elements, mode=mode)
            self.assertTrue(project.results, mode)
            for res in project.results:
                self.assertEqual(res.issues, [], f"{mode} chunk {res.index}")

    def test_fl2va_single_shot(self) -> None:
        project = pipeline.run(parse_file(str(SAMPLE)), mode="FL2VA")
        for res in project.results:
            self.assertEqual(len(res.chunk["shots"]), 1)

    def test_edited_bible_is_used(self) -> None:
        from script2prompt.core.characters import Character

        project = pipeline.run(
            parse_file(str(SAMPLE)), bible=[Character("ELENA", "S1", "tired editor")]
        )
        self.assertEqual([c.description for c in project.bible], ["tired editor"])


class TestExport(unittest.TestCase):
    def test_t2va_pack_shape(self) -> None:
        project = pipeline.run(parse_file(str(SAMPLE)), mode="T2VA")
        pack = pipeline.export_pack(project)
        self.assertIn("prompts.md", pack)
        self.assertIn("manifest.json", pack)
        self.assertIn("characters.md", pack)
        self.assertNotIn("reference_manifest.json", pack)
        self.assertIn("chunk_01.txt", pack)
        manifest = json.loads(pack["manifest.json"])
        self.assertEqual(manifest["mode"], "T2VA")
        self.assertEqual(len(manifest["chunks"]), len(project.results))
        self.assertEqual(manifest["chunks"][0]["speakers"], {"ELENA": "S1"})

    def test_non_t2va_pack_has_reference_manifest(self) -> None:
        project = pipeline.run(parse_file(str(SAMPLE)), mode="R2V")
        pack = pipeline.export_pack(project)
        self.assertIn("reference_manifest.json", pack)
        ref = json.loads(pack["reference_manifest.json"])
        self.assertEqual(ref["mode"], "R2V")
        self.assertIn("subjects", ref["chunks"][0])
        self.assertIn("audios", ref["chunks"][0])

    def test_keyframe_picture_slots(self) -> None:
        elements = parse_file(str(SAMPLE))
        for mode, expected in (("I2VA", 1), ("FL2VA", 2), ("L2VA", 1)):
            ref = pipeline.reference_manifest(pipeline.run(elements, mode=mode))
            self.assertEqual(len(ref["chunks"][0]["pictures"]), expected, mode)
            self.assertTrue(ref["chunks"][0]["instruction_line"], mode)

    def test_write_pack(self) -> None:
        project = pipeline.run(parse_file(str(SAMPLE)), mode="T2VA")
        with tempfile.TemporaryDirectory() as tmp:
            written = pipeline.write_pack(project, tmp)
            for name in written:
                self.assertTrue((Path(tmp) / name).is_file(), name)


class TestInputs(unittest.TestCase):
    def test_parse_bytes_text(self) -> None:
        elements = pipeline.parse_bytes(SAMPLE.read_bytes(), "one_page.txt")
        self.assertEqual(elements[0].kind, "heading")

    def test_parse_bytes_fdx(self) -> None:
        xml = (
            '<FinalDraft><Content><Paragraph Type="Scene Heading">'
            "<Text>INT. ROOM - DAY</Text></Paragraph></Content></FinalDraft>"
        ).encode()
        elements = pipeline.parse_bytes(xml, "custom.fdx")
        self.assertEqual(elements[0].text, "INT. ROOM - DAY")


class TestCli(unittest.TestCase):
    def test_cli_writes_pack(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            with redirect_stdout(io.StringIO()):
                rc = cli.main([str(SAMPLE), "-o", tmp, "-m", "T2VA"])
            self.assertEqual(rc, 0)
            self.assertTrue((Path(tmp) / "prompts.md").is_file())
            self.assertTrue((Path(tmp) / "manifest.json").is_file())

    def test_cli_rejects_bad_mode(self) -> None:
        with redirect_stderr(io.StringIO()), self.assertRaises(SystemExit):
            cli.main([str(SAMPLE), "-m", "NOPE"])


if __name__ == "__main__":
    unittest.main()
