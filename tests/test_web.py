"""Regression test for the web wizard's session-state persistence.

Streamlit is an optional extra that is not installed for the core test run, so
we inject a fake ``streamlit`` module that records widget state and lets us
simulate consecutive reruns (the exact sequence that triggers the bug).
"""
from __future__ import annotations

import sys
import types
import unittest
from unittest import mock


class _Column:
    """Layout column that proxies widget calls back to the fake module."""

    def __init__(self, st: _FakeStreamlit) -> None:
        self._st = st

    def __enter__(self) -> _FakeStreamlit:
        return self._st

    def __exit__(self, *exc: object) -> bool:
        return False

    def __getattr__(self, name: str):
        return getattr(self._st, name)


class _Upload:
    name = "scene.txt"
    size = 42

    def getvalue(self) -> bytes:
        return b"INT. ROOM - DAY\n\nMARA\nHi there.\n"


class _FakeStreamlit(types.ModuleType):
    def __init__(self) -> None:
        super().__init__("streamlit")
        self.session_state: dict = {}
        self.buttons: dict[str, bool] = {}
        self.uploaded = _Upload()

    def set_page_config(self, **kwargs: object) -> None: ...
    def title(self, *args: object, **kwargs: object) -> None: ...
    def caption(self, *args: object, **kwargs: object) -> None: ...
    def info(self, *args: object, **kwargs: object) -> None: ...
    def subheader(self, *args: object, **kwargs: object) -> None: ...
    def markdown(self, *args: object, **kwargs: object) -> None: ...
    def metric(self, *args: object, **kwargs: object) -> None: ...
    def progress(self, *args: object, **kwargs: object) -> None: ...
    def error(self, *args: object, **kwargs: object) -> None: ...
    def warning(self, *args: object, **kwargs: object) -> None: ...
    def success(self, *args: object, **kwargs: object) -> None: ...
    def code(self, *args: object, **kwargs: object) -> None: ...
    def json(self, *args: object, **kwargs: object) -> None: ...
    def download_button(self, *args: object, **kwargs: object) -> None: ...

    def columns(self, spec: object):
        count = spec if isinstance(spec, int) else len(spec)  # type: ignore[arg-type]
        return tuple(_Column(self) for _ in range(count))

    def expander(self, *args: object, **kwargs: object) -> _Column:
        return _Column(self)

    def file_uploader(self, *args: object, **kwargs: object) -> _Upload:
        return self.uploaded

    def radio(self, label: str, options, **kwargs: object):
        return options[0]

    def text_input(self, label: str, value: str = "", **kwargs: object) -> str:
        return value

    def slider(self, label: str, lo, hi, value, step=None):
        return value

    def checkbox(self, *args: object, **kwargs: object) -> bool:
        return False

    def button(self, label: str, **kwargs: object) -> bool:
        return self.buttons.get(label, False)


class TestWebWritePack(unittest.TestCase):
    def test_write_pack_persists_across_rerun(self) -> None:
        fake = _FakeStreamlit()
        written: list[str] = []
        with mock.patch.dict(sys.modules, {"streamlit": fake}):
            from script2prompt.app import web
            from script2prompt.core import pipeline

            with mock.patch.object(
                pipeline, "write_pack", lambda project, out: written.append(out) or ["a.txt"]
            ):
                fake.buttons = {"Generate prompts": True}
                web.main()
                self.assertIn("project", fake.session_state)

                # Rerun triggered by the write button: "Generate prompts" is now
                # False, so the project must survive via session_state.
                fake.buttons = {"Write pack to ./out": True}
                web.main()
        self.assertEqual(written, ["out"])

    def test_no_write_before_generation(self) -> None:
        fake = _FakeStreamlit()
        called: list[tuple] = []
        with mock.patch.dict(sys.modules, {"streamlit": fake}):
            from script2prompt.app import web
            from script2prompt.core import pipeline

            with mock.patch.object(pipeline, "write_pack", lambda *a: called.append(a)):
                fake.buttons = {"Write pack to ./out": True}
                web.main()
        self.assertEqual(called, [])

    def test_new_upload_clears_previous_project(self) -> None:
        fake = _FakeStreamlit()
        written: list[str] = []
        with mock.patch.dict(sys.modules, {"streamlit": fake}):
            from script2prompt.app import web
            from script2prompt.core import pipeline

            with mock.patch.object(
                pipeline, "write_pack", lambda project, out: written.append(out) or []
            ):
                fake.buttons = {"Generate prompts": True}
                web.main()

                # A different file invalidates the cached project, so pressing
                # write must not export the stale one.
                fake.uploaded.size = 99
                fake.buttons = {"Write pack to ./out": True}
                web.main()
        self.assertEqual(written, [])


if __name__ == "__main__":
    unittest.main()
