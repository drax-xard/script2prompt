"""Prerequisite: chunk IDs are stable across re-parses (scene:elem-elem)."""
from __future__ import annotations

import unittest

from script2prompt.core import pipeline
from script2prompt.parsers import plaintext

TWO_SCENES = (
    "INT. NEWSROOM - NIGHT\n\n"
    "Monitors flicker.\n\n"
    "ELENA\nPrint it. I don't care who it burns.\n\n"
    "DANI\nThey'll fire you.\n\n"
    "EXT. ROOFTOP - DAWN\n\n"
    "Leo watches the city wake.\n"
)

LONG_MONOLOGUE = (
    "INT. CELL - NIGHT\n\n"
    "MARA\n" + " ".join(["word"] * 60) + "\n"
)


def _ids(text: str, **kwargs) -> list[str]:
    return [r.stable_id for r in pipeline.run(plaintext.parse(text), **kwargs).results]


class TestStableIds(unittest.TestCase):
    def test_format(self) -> None:
        for sid in _ids(TWO_SCENES):
            self.assertRegex(sid, r"^\d+:\d+-\d+$")

    def test_deterministic(self) -> None:
        self.assertEqual(_ids(TWO_SCENES), _ids(TWO_SCENES))

    def test_scene_index_prefix(self) -> None:
        ids = _ids(TWO_SCENES)
        self.assertTrue(ids[0].startswith("1:"))
        self.assertTrue(ids[-1].startswith("2:"))

    def test_ranges_are_ordered_and_within_scene(self) -> None:
        for sid in _ids(TWO_SCENES):
            first, last = (int(x) for x in sid.split(":")[1].split("-"))
            self.assertLessEqual(first, last)

    def test_split_monologue_shares_source_span(self) -> None:
        ids = _ids(LONG_MONOLOGUE)
        self.assertGreater(len(ids), 1)
        self.assertGreaterEqual(ids[0].split(":")[0], "1")
        for sid in ids:
            self.assertTrue(sid.startswith("1:"))

    def test_manifest_and_budgets_carry_id(self) -> None:
        project = pipeline.run(plaintext.parse(TWO_SCENES))
        expected = [r.stable_id for r in project.results]
        manifest = pipeline.manifest(project)
        self.assertEqual([c["id"] for c in manifest["chunks"]], expected)
        self.assertEqual([c["id"] for c in pipeline.budgets(project)["chunks"]], expected)

    def test_reference_manifest_carries_id(self) -> None:
        project = pipeline.run(plaintext.parse(TWO_SCENES), mode="R2V")
        entries = pipeline.reference_manifest(project)["chunks"]
        self.assertEqual(
            [e["id"] for e in entries], [r.stable_id for r in project.results]
        )


if __name__ == "__main__":
    unittest.main()
