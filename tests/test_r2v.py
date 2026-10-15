"""R2V full-reference tests: manifest, 6-section build, validation."""
from __future__ import annotations

import unittest

from script2prompt.core import chunker, h3_builder, scenes, validator
from script2prompt.core.characters import build_bible
from script2prompt.core.modes import R2V_SECTIONS
from script2prompt.core.ref_manifest import propose
from script2prompt.parsers import plaintext

TEXT = (
    "INT. COFFEE SHOP - DAY\n\n"
    "MARA (30s, tired barista) wipes the counter. Rain taps the windows.\n\n"
    "MARA\nFirst batch of the morning.\n\n"
    "The bell rings. LEO enters, shaking rain from his jacket.\n"
)


def setup():
    parsed = plaintext.parse(TEXT)
    found = scenes.split(parsed)
    bible = build_bible(found)
    chunks = [c for s in found for c in chunker.chunk(s, bible)]
    return bible, chunks


class TestManifest(unittest.TestCase):
    def test_subjects_and_audio(self) -> None:
        bible, chunks = setup()
        manifest = propose(chunks[0], bible)
        kinds = [(s["label"], s["kind"]) for s in manifest["subjects"]]
        self.assertEqual(kinds[0], ("<Subject 1>", "environment"))
        mara = next(s for s in manifest["subjects"] if s["name"] == "MARA")
        self.assertEqual(mara["speaker_id"], "S1")
        self.assertEqual(len(manifest["audios"]), 1)
        audio = manifest["audios"][0]
        self.assertEqual(audio["label"], "<Audio 1>")
        self.assertEqual(audio["subject"], mara["label"])
        self.assertEqual(audio["speaker_id"], "S1")
        self.assertEqual(manifest["pictures"], [])
        self.assertEqual(manifest["videos"], [])
        self.assertEqual(manifest["task_types"], ["reference generation", "audio reference"])


class TestR2VBuild(unittest.TestCase):
    def test_six_sections_in_order(self) -> None:
        bible, chunks = setup()
        prompt = h3_builder.build(chunks[0], bible, mode="R2V")
        positions = [prompt.find(section) for section in R2V_SECTIONS]
        self.assertTrue(all(pos >= 0 for pos in positions))
        self.assertEqual(positions, sorted(positions))
        self.assertEqual(validator.validate(prompt, mode="R2V", duration=chunks[0]["duration"]), [])

    def test_subject_speaker_form(self) -> None:
        bible, chunks = setup()
        prompt = h3_builder.build(chunks[0], bible, mode="R2V")
        self.assertIn("<Subject 2> (S1), Mara, 30s, tired barista", prompt)
        self.assertIn("<d>[English]First batch of the morning.</d>", prompt)
        self.assertIn("[reference generation + audio reference]", prompt)
        self.assertIn("fully_preserved", prompt)

    def test_retention_has_no_speaker_ids(self) -> None:
        bible, chunks = setup()
        prompt = h3_builder.build(chunks[0], bible, mode="R2V")
        retention = prompt.split("retention_analysis:")[1].split("detailed_description:")[0]
        self.assertNotIn("(S1)", retention)


class TestR2VValidation(unittest.TestCase):
    def test_missing_section(self) -> None:
        bible, chunks = setup()
        prompt = h3_builder.build(chunks[0], bible, mode="R2V")
        chopped = prompt.replace("summary:\n", "")
        issues = validator.validate(chopped, mode="R2V", duration=chunks[0]["duration"])
        self.assertTrue(any("section" in i for i in issues))

    def test_bad_marker(self) -> None:
        bible, chunks = setup()
        prompt = h3_builder.build(chunks[0], bible, mode="R2V")
        broken = prompt.replace("fully_preserved", "mostly_kept", 1)
        issues = validator.validate(broken, mode="R2V", duration=chunks[0]["duration"])
        self.assertTrue(any("marker" in i for i in issues))

    def test_undefined_label(self) -> None:
        bible, chunks = setup()
        prompt = h3_builder.build(chunks[0], bible, mode="R2V")
        broken = prompt.replace("<Subject 2> (S1), Mara", "<Subject 9> (S1), Mara")
        issues = validator.validate(broken, mode="R2V", duration=chunks[0]["duration"])
        self.assertTrue(any("undefined" in i for i in issues))


if __name__ == "__main__":
    unittest.main()
