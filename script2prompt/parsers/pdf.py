"""PDF screenplay parser (extract text, then delegate to plaintext).

Requires the optional ``pdf`` extra (pypdf), imported lazily so the core works
without any third-party installs. Install with ``.venv/bin/pip install .[pdf]``.

Uses pypdf's ``layout`` extraction when available: screenplays are hard-wrapped
into narrow columns with no blank lines between blocks, which defeats the
plain-text line heuristics (headings get swallowed into one giant dialogue
block). Layout mode keeps the paragraph line breaks and indentation, so the
plain-text parser sees the same block structure it does for `.txt`/`.fountain`.
"""
from __future__ import annotations

from . import plaintext
from .base import Element

_INSTALL = "PDF support needs the 'pdf' extra: .venv/bin/pip install .[pdf]"


def _page_text(page) -> str:
    """Extract one page, preferring layout mode for paragraph structure."""
    try:
        text = page.extract_text(extraction_mode="layout")
    except TypeError:  # older pypdf without extraction_mode
        text = page.extract_text()
    return text or ""


def extract_text(path: str) -> str:
    """Extract the full text of a PDF, preserving per-block line breaks."""
    try:
        import pypdf
    except ImportError as exc:
        raise ImportError(_INSTALL) from exc
    reader = pypdf.PdfReader(path)
    return "\n".join(_page_text(page) for page in reader.pages)


def parse(path: str) -> list[Element]:
    """Extract text from a PDF and parse it with the plain-text heuristics."""
    return plaintext.parse(extract_text(path))
