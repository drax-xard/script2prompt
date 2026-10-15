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

_ACTION_INTRO = re.compile(r"^([A-Z][A-Z\s'\-]*?)\s*\(([^)]*)\)\s+\S")
_CAPS_NAME = re.compile(r"\b([A-Z]{2,}(?:\s+[A-Z]{2,})?)\b")
_NOISE = frozenset({"INT", "EXT", "CUT", "FADE", "TO"})


@dataclass
class Character:
    name: str  # normalized cue form, e.g. "MARY JANE"
    speaker_id: str | None  # S1.. for vocal characters, None otherwise
    description: str  # traits from action intro, "" when unknown


def title(name: str) -> str:
    """Human-readable form of a normalized cue name."""
    return " ".join(word.capitalize() for word in name.split())


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
    last_cue: str | None = None

    def seen_note(name: str) -> None:
        if not name:
            return
        mentions[name] += 1
        if name not in seen:
            seen.append(name)

    for scene in scenes:
        last_cue = None
        for el in scene["elements"]:
            if el.kind == "character":
                name = el.meta.get("name", "")
                seen_note(name)
                if name:
                    backed.add(name)
                last_cue = name or None
            elif el.kind == "dialogue":
                if last_cue and last_cue not in vocal_pos:
                    vocal_pos[last_cue] = len(vocal_pos)
            elif el.kind == "action":
                text = el.text.strip()
                m = _ACTION_INTRO.match(text)
                if m:
                    intro = re.sub(r"\s+", " ", m.group(1)).strip().upper()
                    if intro:
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
