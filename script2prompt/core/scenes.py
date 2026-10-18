"""Scene splitter: group elements by INT./EXT. heading."""
from __future__ import annotations

from script2prompt.parsers.base import Element


def split(elements: list[Element]) -> list[dict]:
    """Group elements into scenes.

    Each scene is ``{"index": int, "heading": str, "context": str, "elements":
    [...]}`` with a 1-based ``index`` (used in stable chunk IDs). Elements before
    the first heading form a cold-open scene with empty heading/context.
    """
    scenes: list[dict] = []
    current: dict | None = None
    for el in elements:
        if el.kind == "heading":
            if current is not None:
                scenes.append(current)
            current = {"heading": el.text, "context": el.text, "elements": []}
        else:
            if current is None:
                current = {"heading": "", "context": "", "elements": []}
            current["elements"].append(el)
    if current is not None:
        scenes.append(current)
    for number, scene in enumerate(scenes, start=1):
        scene["index"] = number
    return scenes
