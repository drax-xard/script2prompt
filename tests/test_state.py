"""Prerequisite: project state helpers are pure and testable (no Streamlit)."""
from __future__ import annotations

import unittest

from script2prompt.core import config, pipeline
from script2prompt.core.characters import Character


class TestDefaultSettings(unittest.TestCase):
    def test_from_config_defaults(self) -> None:
        cfg = config.load("does-not-exist.toml", "does-not-exist-local.toml")
        settings = pipeline.default_settings(cfg)
        self.assertEqual(settings["mode"], "T2VA")
        self.assertEqual(settings["shots_max"], 3)
        self.assertFalse(settings["use_llm"])

    def test_clamps_high(self) -> None:
        settings = pipeline.default_settings(
            {"project": {"mode": "BOGUS", "style": "X", "duration": 99.0, "shots_max": 9}}
        )
        self.assertEqual(settings["mode"], "T2VA")
        self.assertEqual(settings["duration"], 10.0)
        self.assertEqual(settings["shots_max"], 3)

    def test_clamps_low(self) -> None:
        settings = pipeline.default_settings(
            {"project": {"duration": 0.1, "shots_max": 0}}
        )
        self.assertEqual(settings["duration"], 5.0)
        self.assertEqual(settings["shots_max"], 1)

    def test_keeps_valid_mode(self) -> None:
        settings = pipeline.default_settings({"project": {"mode": "R2V"}})
        self.assertEqual(settings["mode"], "R2V")


class TestBibleRows(unittest.TestCase):
    def test_round_trip(self) -> None:
        bible = [Character("MARA", "S1", "30s, tired barista")]
        rows = pipeline.bible_rows(bible)
        self.assertEqual(rows[0]["name"], "Mara")
        self.assertEqual(rows[0]["speaker_id"], "S1")
        back = pipeline.bible_from_rows(rows)
        self.assertEqual(back[0].name, "MARA")
        self.assertEqual(back[0].speaker_id, "S1")
        self.assertEqual(back[0].description, "30s, tired barista")

    def test_blank_name_dropped(self) -> None:
        self.assertEqual(pipeline.bible_from_rows([{"name": "  "}]), [])

    def test_blank_speaker_becomes_none(self) -> None:
        rows = [{"name": "Mara", "speaker_id": "", "description": ""}]
        self.assertIsNone(pipeline.bible_from_rows(rows)[0].speaker_id)

    def test_empty_speaker_rendered_blank(self) -> None:
        rows = pipeline.bible_rows([Character("MARA", None, "")])
        self.assertEqual(rows[0]["speaker_id"], "")


if __name__ == "__main__":
    unittest.main()
