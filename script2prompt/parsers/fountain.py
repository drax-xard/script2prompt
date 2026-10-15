"""Fountain markup parser (subset).

On top of the plain-text heuristics, handles Fountain forced markers:
`.Heading`, `@Character`, `> Transition`. Transition lines keep their text
without the marker in a real implementation; here the raw text is preserved
and the marker is recorded in meta.
"""
from __future__ import annotations

from . import plaintext
from .base import Element


def _forced_heading(line: str) -> bool:
    s = line.strip()
    return len(s) > 2 and s.startswith(".") and s[1].isalnum()


def parse(text: str) -> list[Element]:
    """Parse Fountain-markup screenplay into elements."""
    elements: list[Element] = []
    in_dialogue = False
    for lineno, raw in enumerate(text.splitlines(), start=1):
        line = raw.strip()
        if not line:
            in_dialogue = False
            continue
        if _forced_heading(line):
            elements.append(Element("heading", line[1:].strip(), {"line": lineno}))
            in_dialogue = False
        elif line.startswith("@") and len(line) > 1:
            name, ext = plaintext.normalize_cue(line)
            elements.append(
                Element("character", line, {"name": name, "extension": ext, "line": lineno})
            )
            in_dialogue = True
        elif line.startswith(">") and len(line) > 1:
            elements.append(Element("transition", line[1:].strip(), {"line": lineno}))
            in_dialogue = False
        elif plaintext._is_heading(line):
            elements.append(Element("heading", line, {"line": lineno}))
            in_dialogue = False
        elif plaintext._is_transition(line):
            elements.append(Element("transition", line, {"line": lineno}))
            in_dialogue = False
        elif plaintext._looks_like_cue(line):
            name, ext = plaintext.normalize_cue(line)
            elements.append(
                Element("character", line, {"name": name, "extension": ext, "line": lineno})
            )
            in_dialogue = True
        elif plaintext._is_parenthetical(line) and in_dialogue:
            elements.append(Element("parenthetical", line, {"line": lineno}))
        elif in_dialogue:
            elements.append(Element("dialogue", line, {"line": lineno}))
        else:
            elements.append(Element("action", line, {"line": lineno}))
    return elements
