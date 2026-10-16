"""PDF screenplay parser (extract text, then delegate to plaintext).

Requires the optional ``pdf`` extra (pypdf), imported lazily so the core works
without any third-party installs. Install with ``.venv/bin/pip install .[pdf]``.
"""
from __future__ import annotations

from . import plaintext
from .base import Element

_INSTALL = "PDF support needs the 'pdf' extra: .venv/bin/pip install .[pdf]"


def extract_text(path: str) -> str:
    """Extract the full text of a PDF, one page per line block."""
    try:
        import pypdf
    except ImportError as exc:
        raise ImportError(_INSTALL) from exc
    reader = pypdf.PdfReader(path)
    return "\n".join(page.extract_text() or "" for page in reader.pages)


def parse(path: str) -> list[Element]:
    """Extract text from a PDF and parse it with the plain-text heuristics."""
    return plaintext.parse(extract_text(path))
