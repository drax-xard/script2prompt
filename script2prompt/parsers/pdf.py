"""PDF screenplay parser (extract text, then delegate to plaintext).

Requires the optional ``pdf`` extra (pypdf), imported lazily so the core
works without any third-party installs. Install with ``.venv/bin/pip install .[pdf]``.
"""
from __future__ import annotations

from .base import Element


def parse(path: str) -> list[Element]:
    """Extract text from PDF and parse. TODO: implement (Milestone 5)."""
    try:
        import pypdf  # noqa: F401
    except ImportError as exc:
        raise ImportError(
            "PDF support needs the 'pdf' extra: .venv/bin/pip install .[pdf]"
        ) from exc
    raise NotImplementedError
