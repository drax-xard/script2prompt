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

# Action intro: NAME(S) with traits, allowing joint connectors ("MARA AND LEO",
# "ELENA & MARA", "MARY JANE"). The names are split into individuals later.
_ACTION_INTRO = re.compile(
    r"\b([A-Z][A-Z'\-]+(?:(?:\s+AND\s+|\s*&\s*|\s+)[A-Z][A-Z'\-]+){0,3})\s*\(([^)]*)\)"
)
_TRAITS_LIKE = re.compile(r"[\d,]")
# Alternate intro form: "DANI, a nervous junior reporter, ..." (no parenthetical).
# Guarded by a comma + article so ordinary comma clauses are ignored.
_APPOSITIVE_INTRO = re.compile(
    r"\b([A-Z][A-Z'\-]+)\s*,\s*(?:a|an|the)\s+([A-Za-z][^,.;]{2,60}?)(?=,|\.|;|$)"
)
# A multi-word caps name must not swallow a connector word ("ELENA AND").
_CAPS_NAME = re.compile(
    r"\b([A-Z](?:['\-]?[A-Z])+(?:\s+(?!(?:AND|OR|THE|AN|A)\b)[A-Z](?:['\-]?[A-Z])+)?)\b"
)
_STOP = frozenset({"AND", "OR", "THE", "AN", "A"})
_NOISE = frozenset({"INT", "EXT", "EST", "CUT", "FADE", "TO"}) | _STOP
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
    ``O'Brien``). Runs touching a digit are designators and are left as-is
    (``C3PO`` stays ``C3PO``, not ``C3Po``).
    """
    def _cap(match: re.Match) -> str:
        start, end = match.span()
        before = name[start - 1] if start > 0 else ""
        after = name[end] if end < len(name) else ""
        if before.isdigit() or after.isdigit():
            return match.group(0)
        token = match.group(0)
        # A lone "s" after an apostrophe is possessive, not a surname capital
        # ("WILL'S DATE" -> "Will's Date", but "O'BRIEN" -> "O'Brien").
        if before == "'" and token.lower() == "s" and not after.isalpha():
            return token.lower()
        return token.capitalize()

    return re.sub(r"[A-Za-z]+", _cap, name)


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
                    # A joint intro ("MARA AND LEO (30s)") names each character,
                    # not one phantom "MARA AND LEO".
                    for name in split_joint(intro) or [intro]:
                        if name not in traits:
                            traits[name] = m.group(2).strip()
                        backed.add(name)
                        seen_note(name)
                for m in _APPOSITIVE_INTRO.finditer(text):
                    name = m.group(1).upper()
                    desc = re.sub(r"\s+", " ", m.group(2)).strip()
                    if name in _NOISE or name in traits or len(desc.split()) > 8:
                        continue
                    traits[name] = desc
                    backed.add(name)
                    seen_note(name)
                for found in _CAPS_NAME.findall(text):
                    candidate = re.sub(r"\s+", " ", found).strip().upper()
                    for name in split_joint(candidate) or [candidate]:
                        if name not in _NOISE:
                            seen_note(name)

    order = [name for name in seen if name in backed or mentions[name] >= 2]
    bible = []
    for name in order:
        if name in vocal_pos:
            speaker_id: str | None = f"S{vocal_pos[name] + 1}"
        else:
            speaker_id = None
        bible.append(Character(name, speaker_id, traits.get(name, "")))
    return bible
