"""Plain-text screenplay parser (heuristic).

Rules: scene headings (`INT./EXT.`), transitions (`CUT TO:`), character cues
(short ALL-CAPS lines, optional trailing `(O.S.)`-style extension), dialogue
(lines following a cue until a blank line), parentheticals, action (rest).
"""
from __future__ import annotations

import re

from .base import Element

_HEADING = re.compile(r"^(INT|EXT|EST)[\.\-/]\s*\S", re.IGNORECASE)
_TRANSITION = re.compile(r"^(FADE (IN|OUT|TO)|SMASH CUT|MATCH CUT|DISSOLVE|CUT)\b")
_CUE_PAREN = re.compile(r"^(?P<name>.*?)\s*(?P<ext>\([^)]*\)(?:\s*\([^)]*\))*)\s*$")
_PUNCT_END = frozenset(".!?,;:")


def _is_heading(line: str) -> bool:
    s = line.strip()
    if not _HEADING.match(s):
        return False
    if s.isupper():
        return True
    # Mixed-case slugs are accepted only with a time separator, so a dialogue
    # line that merely starts "EXT." (e.g. "EXT. That's where I left it.") is
    # not mistaken for a scene heading.
    return " - " in s


def _is_transition(line: str) -> bool:
    s = line.strip()
    if s.startswith(">") and len(s) > 1:
        return True
    if len(s) > 40 or s != s.upper() or not any(c.isalpha() for c in s):
        return False
    return s.endswith("TO:") or bool(_TRANSITION.match(s))


def _is_parenthetical(line: str) -> bool:
    s = line.strip()
    return len(s) > 2 and s.startswith("(") and s.endswith(")")


def _looks_like_cue(line: str, next_line: str | None = None) -> bool:
    s = line.strip()
    if s.startswith("@"):
        s = s[1:].strip()
    if not s or len(s) > 35 or len(s.split()) > 5:
        return False
    if not any(c.isalpha() for c in s):
        return False
    if s != s.upper():
        return False
    if s[-1] in _PUNCT_END:
        return False
    if _is_transition(line):
        return False
    if next_line is not None and not next_line.strip():
        # A cue must be followed by dialogue/parenthetical on the next line; a
        # lone ALL-CAPS action beat ("THUNDER") is not a character.
        return False
    return True


def normalize_cue(text: str) -> tuple[str, str]:
    """Return (NAME, extension) from a character cue line."""
    s = text.strip()
    if s.startswith("@"):
        s = s[1:].strip()
    m = _CUE_PAREN.match(s)
    if m and m.group("name").strip():
        return m.group("name").strip().upper(), m.group("ext").strip()
    return s.upper(), ""


def parse(text: str) -> list[Element]:
    """Parse freeform plain-text screenplay into elements."""
    lines = text.splitlines()
    elements: list[Element] = []
    in_dialogue = False
    for lineno, raw in enumerate(lines, start=1):
        line = raw.strip()
        if not line:
            in_dialogue = False
            continue
        next_line = lines[lineno].strip() if lineno < len(lines) else ""
        if _is_heading(line):
            elements.append(Element("heading", line, {"line": lineno}))
            in_dialogue = False
        elif _is_transition(line):
            elements.append(Element("transition", line, {"line": lineno}))
            in_dialogue = False
        elif _looks_like_cue(line, next_line):
            name, ext = normalize_cue(line)
            elements.append(
                Element("character", line, {"name": name, "extension": ext, "line": lineno})
            )
            in_dialogue = True
        elif _is_parenthetical(line) and in_dialogue:
            elements.append(Element("parenthetical", line, {"line": lineno}))
        elif in_dialogue:
            elements.append(Element("dialogue", line, {"line": lineno}))
        else:
            elements.append(Element("action", line, {"line": lineno}))
    return elements
