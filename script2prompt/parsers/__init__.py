"""Parser dispatch: choose a parser by file extension.

Text formats (``.txt``/``.text``/``.fountain``/``.spmd``) are read as UTF-8 and
handed to the plain-text or Fountain parser; ``.fdx`` and ``.pdf`` are passed to
their path-based parsers. Unknown extensions fall back to the plain-text
heuristic.
"""
from __future__ import annotations

from pathlib import Path

from .base import Element

_TEXT = {".txt": "plaintext", ".text": "plaintext", ".fountain": "fountain", ".spmd": "fountain"}
_PATH = {".fdx": "fdx", ".pdf": "pdf"}


def parse_file(path: str | Path) -> list[Element]:
    """Parse a screenplay file into elements, picking the parser by suffix."""
    from . import fdx, fountain, pdf, plaintext

    modules = {"plaintext": plaintext, "fountain": fountain, "fdx": fdx, "pdf": pdf}
    p = Path(path)
    suffix = p.suffix.lower()
    if suffix in _PATH:
        return modules[_PATH[suffix]].parse(str(p))
    module = modules[_TEXT.get(suffix, "plaintext")]
    raw = p.read_bytes()
    if b"\x00" in raw:
        raise ValueError(
            f"unsupported binary file: {p} (expected a text screenplay, .fdx, or .pdf)"
        )
    return module.parse(raw.decode("utf-8", errors="replace"))
