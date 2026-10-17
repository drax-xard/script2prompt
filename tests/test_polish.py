"""Milestone 7 polish tests: budget summary, lint, CLI config/flags."""
from __future__ import annotations

import json
import tempfile
import unittest
from contextlib import redirect_stdout
from io import StringIO
from pathlib import Path

from script2prompt import __main__ as cli
from script2prompt.core import config, pipeline, validator
from script2prompt.parsers import parse_file, plaintext

SAMPLE = Path("samples/one_page.txt")


class TestBudgets(unittest.TestCase):
    def test_summary_shape(self) -> None:
        project = pipeline.run(parse_file(str(SAMPLE)), mode="T2VA")
        summary = pipeline.budgets(project)
        self.assertEqual(summary["char_budget"], validator.CHAR_BUDGET)
        self.assertEqual(len(summary["chunks"]), len(project.results))
        self.assertGreater(summary["total_duration"], 0)
        self.assertEqual(summary["over_budget"], [])
        for ch in summary["chunks"]:
            self.assertLessEqual(ch["char_ratio"], 1.0)
            self.assertLessEqual(ch["shots"], 3)

    def test_over_budget_flagged(self) -> None:
        project = pipeline.run(parse_file(str(SAMPLE)), mode="T2VA")
        project.results[0].prompt = "x" * (validator.CHAR_BUDGET + 10)
        summary = pipeline.budgets(project)
        self.assertEqual(summary["over_budget"], [project.results[0].index])


class TestLint(unittest.TestCase):
    def test_clean_project(self) -> None:
        project = pipeline.run(parse_file(str(SAMPLE)), mode="T2VA")
        self.assertEqual(pipeline.lint(project), [])

    def test_chunk_issues_aggregated(self) -> None:
        project = pipeline.run(parse_file(str(SAMPLE)), mode="T2VA")
        project.results[0].issues = ["boom"]
        self.assertIn(f"chunk {project.results[0].index}: boom", pipeline.lint(project))

    def test_no_characters_and_no_chunks(self) -> None:
        empty = pipeline.run([])
        warnings = pipeline.lint(empty)
        self.assertTrue(any("no characters" in w for w in warnings))
        self.assertTrue(any("no chunks" in w for w in warnings))

    def test_no_character_screenplay(self) -> None:
        els = plaintext.parse("INT. R - DAY\n\nthe room is quiet and empty.\n")
        project = pipeline.run(els)
        self.assertTrue(any("no characters" in w for w in pipeline.lint(project)))


class TestClamping(unittest.TestCase):
    def test_duration_clamped(self) -> None:
        els = parse_file(str(SAMPLE))
        self.assertEqual(pipeline.run(els, duration=0).duration, 5.0)
        self.assertEqual(pipeline.run(els, duration=999).duration, 10.0)

    def test_shots_clamped(self) -> None:
        els = parse_file(str(SAMPLE))
        self.assertEqual(pipeline.run(els, shots_max=0).shots_max, 1)
        self.assertEqual(pipeline.run(els, shots_max=9).shots_max, 3)


class TestCliPolish(unittest.TestCase):
    def _run(self, argv: list[str]) -> str:
        buf = StringIO()
        with redirect_stdout(buf):
            self.rc = cli.main(argv)
        return buf.getvalue()

    def test_shots_flag(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            self._run([str(SAMPLE), "-o", tmp, "--shots", "1"])
            self.assertEqual(self.rc, 0)
            manifest = json.loads((Path(tmp) / "manifest.json").read_text(encoding="utf-8"))
            for chunk in manifest["chunks"]:
                self.assertLessEqual(len(chunk["shots"]), 1)

    def test_config_flag(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            cfg = Path(tmp) / "custom.toml"
            cfg.write_text('[project]\nmode = "I2VA"\n', encoding="utf-8")
            self._run([str(SAMPLE), "-o", tmp, "--config", str(cfg)])
            manifest = json.loads((Path(tmp) / "manifest.json").read_text(encoding="utf-8"))
            self.assertEqual(manifest["mode"], "I2VA")

    def test_strict_exit_code(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            clean = Path(tmp) / "clean.txt"
            clean.write_text("INT. R - DAY\n\nELENA\nHi.\n", encoding="utf-8")
            self._run([str(clean), "-o", tmp, "--strict"])
            self.assertEqual(self.rc, 0)

            silent = Path(tmp) / "silent.txt"
            silent.write_text("INT. R - DAY\n\nthe room is quiet and empty.\n", encoding="utf-8")
            self._run([str(silent), "-o", tmp, "--strict"])
            self.assertEqual(self.rc, 1)


class TestConfigPath(unittest.TestCase):
    def test_explicit_path(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            cfg = Path(tmp) / "c.toml"
            cfg.write_text('[project]\nmode = "L2VA"\nduration = 6.0\n', encoding="utf-8")
            loaded = config.load(cfg, Path(tmp) / "missing.toml")
            self.assertEqual(loaded["project"]["mode"], "L2VA")
            self.assertEqual(loaded["project"]["duration"], 6.0)


if __name__ == "__main__":
    unittest.main()
