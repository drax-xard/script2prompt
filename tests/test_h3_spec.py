"""h3_spec is the single source of truth for the H3 rules."""
from __future__ import annotations

import unittest

from script2prompt.core import chunker, h3_spec, modes, prompts, validator


class TestSingleSource(unittest.TestCase):
    def test_modes_reexport_spec(self) -> None:
        self.assertEqual(modes.MODES, h3_spec.MODES)
        self.assertEqual(modes.BASE_FIELDS, h3_spec.BASE_FIELDS)
        self.assertEqual(modes.R2V_SECTIONS, h3_spec.R2V_SECTIONS)

    def test_validator_uses_spec_budgets(self) -> None:
        self.assertEqual(validator.CHAR_BUDGET, h3_spec.CHAR_BUDGET)
        self.assertEqual(validator.FIELDS, h3_spec.BASE_FIELDS)

    def test_chunker_uses_spec_seconds(self) -> None:
        self.assertEqual(chunker.MIN_SECONDS, h3_spec.MIN_SECONDS)
        self.assertEqual(chunker.CAP_SECONDS, h3_spec.CAP_SECONDS)
        self.assertEqual(chunker.DIALOGUE_WPS, h3_spec.DIALOGUE_WPS)
        self.assertEqual(chunker.ACTION_WPS, h3_spec.ACTION_WPS)

    def test_prompts_embed_spec_values(self) -> None:
        for mode in h3_spec.MODES:
            self.assertIn(str(h3_spec.CHAR_BUDGET), prompts.system_prompt(mode))
        common = prompts.system_prompt("T2VA")
        self.assertIn(str(h3_spec.MAX_SHOTS), common)
        for motion in h3_spec.CAMERA_MOTIONS:
            self.assertIn(motion, common)

    def test_r2v_prompt_lists_retention_markers(self) -> None:
        r2v = prompts.system_prompt("R2V")
        for marker in h3_spec.VISUAL_MARKERS + h3_spec.AUDIO_MARKERS:
            self.assertIn(marker, r2v)

    def test_validator_accepts_every_retention_marker(self) -> None:
        visual = "\n".join(
            f"<Subject {i}> (appears throughout): {m} - kept."
            for i, m in enumerate(h3_spec.VISUAL_MARKERS, start=1)
        )
        prompt = (
            "subject_definitions:\n<Subject 1> is the room.\n\n"
            "summary:\n[reference generation] A shot.\n\n"
            f"retention_analysis:\n{visual}\n\n"
            "detailed_description:\nLive-action.\n[Shot 1] The room.\n\n"
            "overall_soundscape:\nA hum.\n\n"
            "non_diegetic_music:\nN/A"
        )
        issues = validator.validate(prompt, mode="R2V", duration=8.0)
        self.assertFalse([i for i in issues if "retention marker" in i])


if __name__ == "__main__":
    unittest.main()
