"""Character bible: stable descriptions + speaker IDs (S1, S2, ...).

Speaker IDs count *voices* in order of first vocalization (H3 rule): the
first character with a dialogue line is S1. Characters mentioned in action
but never speaking get ``speaker_id=None``. Descriptions come from action
intros of the form ``NAME (traits) ...`` and are captured once, reused
verbatim afterwards.
"""
from __future__ import annotations

import re
from collections import Counter
from dataclasses import dataclass

_ACTION_INTRO = re.compile(r"\b([A-Z][A-Z'\-]+(?:\s+[A-Z][A-Z'\-]+){0,2})\s*\(([^)]*)\)")
_TRAITS_LIKE = re.compile(r"[\d,]")
_CAPS_NAME = re.compile(r"\b([A-Z](?:['\-]?[A-Z])+(?:\s+[A-Z](?:['\-]?[A-Z])+)?)\b")
_NOISE = frozenset({"INT", "EXT", "EST", "CUT", "FADE", "TO"})
# Joint speaker cue connectors (guide §4.4): "ELENA AND MARA", "ELENA & MARA",
# "ELENA/MARA", "ELENA + MARA". Requires whole-word "and" so names like
# "ALEXANDER" are not split.
_JOINT = re.compile(r"\s*(?:/|&|\+|\band\b)\s*", re.IGNORECASE)


@dataclass
class Character:
    name: str  # normalized cue form, e.g. "MARY JANE"
    speaker_id: str | None  # S1.. for vocal characters, None otherwise
    description: str  # traits from action intro, "" when unknown


def split_joint(name: str) -> list[str]:
    """Split a joint speaker cue into individual names (guide §4.4).

    Returns an empty list for an ordinary single-name cue, so callers fall back
    to the whole name. The connector is dropped and each part upper-cased:
    ``"ELENA AND MARA"`` -> ``["ELENA", "MARA"]``. Every part must be at least
    two characters so an ampersand inside a single name (``AT&T``) is not split.
    """
    if not name:
        return []
    parts = [p.strip().upper() for p in _JOINT.split(name) if p.strip()]
    if len(parts) > 1 and all(len(p) >= 2 for p in parts):
        return parts
    return []


def title(name: str) -> str:
    """Human-readable form of a normalized cue name.

    Capitalizes each alphabetic run so hyphenated and apostrophized names keep
    their interior capitals (``MARY-JANE`` -> ``Mary-Jane``, ``O'BRIEN`` ->
    ``O'Brien``).
    """
    return re.sub(r"[A-Za-z]+", lambda m: m.group(0).capitalize(), name.lower())


def build_bible(scenes: list[dict]) -> list[Character]:
    """Build the character bible for parsed scenes, in first-appearance order.

    Cue names and ``NAME (traits)`` intro names always join. Bare ALL-CAPS
    mentions in action lines (which also match props, devices, and interjections
    like TV/DAY/OK) join only on a second mention, as recurring silent characters.
    """
    seen: list[str] = []
    mentions: Counter[str] = Counter()
    traits: dict[str, str] = {}
    vocal_pos: dict[str, int] = {}
    backed: set[str] = set()
    last_cue: list[str] = []

    def seen_note(name: str) -> None:
        if not name:
            return
        mentions[name] += 1
        if name not in seen:
            seen.append(name)

    for scene in scenes:
        last_cue = []
        for el in scene["elements"]:
            if el.kind == "character":
                raw = el.meta.get("name", "")
                names = split_joint(raw) or ([raw] if raw else [])
                for name in names:
                    seen_note(name)
                    backed.add(name)
                last_cue = names
            elif el.kind == "dialogue":
                for name in last_cue:
                    if name and name not in vocal_pos:
                        vocal_pos[name] = len(vocal_pos)
            elif el.kind == "action":
                text = el.text.strip()
                for m in _ACTION_INTRO.finditer(text):
                    intro = re.sub(r"\s+", " ", m.group(1)).strip().upper()
                    # Only treat NAME (…) as a character intro when the
                    # parenthetical looks like traits (age/comma), so props
                    # like "THE SIGN (unreadable)" are not mistaken for people.
                    if not intro or intro in _NOISE or not _TRAITS_LIKE.search(m.group(2)):
                        continue
                    if intro not in traits:
                        traits[intro] = m.group(2).strip()
                    backed.add(intro)
                    seen_note(intro)
                for found in _CAPS_NAME.findall(text):
                    candidate = re.sub(r"\s+", " ", found).strip().upper()
                    if candidate not in _NOISE:
                        seen_note(candidate)

    order = [name for name in seen if name in backed or mentions[name] >= 2]
    bible = []
    for name in order:
        if name in vocal_pos:
            speaker_id: str | None = f"S{vocal_pos[name] + 1}"
        else:
            speaker_id = None
        bible.append(Character(name, speaker_id, traits.get(name, "")))
    return bible
