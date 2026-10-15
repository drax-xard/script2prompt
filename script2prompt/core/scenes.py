"""Scene splitter: group elements by INT./EXT. heading."""
from __future__ import annotations

from .characters import Character
from script2prompt.parsers.base import Element


def split(elements: list[Element]) -> list[dict]:
    """Return [{'heading': str, 'context': str, 'elements': [...]}]. TODO: Milestone 1."""
    raise NotImplementedError
