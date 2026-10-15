"""Scene splitter: group elements by INT./EXT. heading."""
from __future__ import annotations

from script2prompt.parsers.base import Element


def split(elements: list[Element]) -> list[dict]:
    """Group elements into scenes.

    Each scene is ``{"heading": str, "context": str, "elements": [...]}``.
    Elements before the first heading form a cold-open scene with empty
    heading/context.
    """
    scenes: list[dict] = []
    current = {"heading": "", "context": "", "elements": []}
    for el in elements:
        if el.kind == "heading":
            if current["elements"] or current["heading"]:
                scenes.append(current)
            current = {"heading": el.text, "context": el.text, "elements": []}
        else:
            current["elements"].append(el)
    if current["elements"] or current["heading"]:
        scenes.append(current)
    return scenes
