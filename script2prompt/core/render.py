"""Shared prose helpers for the deterministic prompt builders.

Both the base-mode builder (``fallback``) and the full-reference builder
(``r2v``) render prose the same way, so the text utilities, the naturalized
scene phrase, the camera-motion picker, the ``overall_soundscape`` derivation,
and the ``non_diegetic_music`` rule live here once.
"""
from __future__ import annotations

import re

from .ref_manifest import slugline_parts

__all__ = [
    "clean",
    "finish",
    "scene_noun",
    "scene_phrase",
    "seed_key",
    "camera_sentence",
    "cut_lead",
    "soundscape_sentences",
    "music_line",
]

_VOWELS = "aeiou"

# Slugline time token -> natural phrase. An empty string drops the clause.
_TIME_PHRASES = {
    "night": "at night",
    "day": "during the day",
    "dawn": "at dawn",
    "dusk": "at dusk",
    "morning": "in the morning",
    "evening": "in the evening",
    "afternoon": "in the afternoon",
    "continuous": "",
    "later": "later",
    "moment": "",
}

# Deterministic camera pools chosen by shot content and a stable seed. Motion
# type, optional amplitude/speed follow the guide's camera vocabulary.
_ESTABLISH_CAMERAS = (
    "The camera pushes in with small amplitude at slow speed.",
    "The camera holds a static shot.",
    "The camera pans left with small amplitude at slow speed.",
    "The camera trucks right at slow speed.",
)
_DIALOGUE_CAMERAS = (
    "The camera holds a static shot.",
    "The camera pushes in with small amplitude at slow speed.",
    "The camera pans right with small amplitude at slow speed.",
)
_ACTION_CAMERAS = (
    "The camera tracks the movement.",
    "The camera pans right, following the action.",
    "The camera pulls back at slow speed.",
    "The camera holds a static shot.",
)
_CUT_LEADS = (
    "the camera cuts to a new angle",
    "the shot cuts to a closer view",
    "the camera cuts to a wider view",
)

# Action text -> sound phrase. Conservative: only cues that are almost always
# audible, so the derived soundscape describes real sounds instead of restating
# the action verbatim (which used to leak character introductions and names).
_SOUND_CUES = (
    (r"\b(hums?|humming)\b", "a low electrical hum"),
    (r"\b(dings?|dinging|chimes?|chiming)\b", "a chime"),
    (r"\b(clatter|clink|clank|rattle|rattles|rattling)\b", "a metallic clatter"),
    (r"\brain(s|ing|ed)?\b", "falling rain"),
    (r"\bfootsteps?\b", "footsteps"),
    (r"\b(slams?|slammed)\b", "a sharp slam"),
    (r"\bbuzz(es|ed|ing)?\b", "a low buzz"),
    (r"\bwhispers?|whispering\b", "whispering"),
    (r"\b(laughs?|laughed|laughing|laughter)\b", "soft laughter"),
    (r"\b(breath(e|es|ing)|pant(s|ed|ing)?)\b", "shallow breathing"),
    (r"\bwind\b", "wind"),
    (r"\btraffic\b", "distant traffic"),
)
# Only an explicit, audience-facing score switches off the default N/A.
_MUSIC_HINTS = re.compile(r"\b(score|soundtrack|non[- ]diegetic)\b", re.IGNORECASE)


def clean(text: str) -> str:
    """Collapse internal whitespace and strip the ends."""
    return re.sub(r"\s+", " ", text.strip())


def finish(sentence: str) -> str:
    """Clean a sentence and guarantee terminal punctuation."""
    sentence = clean(sentence)
    if sentence and sentence[-1] not in ".!?":
        sentence += "."
    return sentence


def _article(word: str) -> str:
    return "an" if word[:1].lower() in _VOWELS else "a"


def scene_noun(context: str) -> str:
    """Lower-cased location noun from a slugline (``""`` when absent)."""
    location, _ = slugline_parts(context)
    return location.lower() if location else ""


def scene_phrase(context: str) -> str:
    """Natural setting phrase, e.g. ``a newsroom at night``.

    Never returns the raw slugline; ``""`` when the chunk has no slugline.
    """
    location, time = slugline_parts(context)
    if not location:
        return ""
    noun = location.lower()
    phrase = f"{_article(noun)} {noun}"
    key = time.strip().lower()
    if key:
        if key in _TIME_PHRASES:
            mapped = _TIME_PHRASES[key]
            if mapped:
                phrase += f" {mapped}"
        else:
            phrase += f" at {key}"
    return phrase


def seed_key(context: str, elements: list) -> str:
    """Stable per-shot seed source: slugline plus the shot's opening beat.

    ``hash()`` is salted per process, so a plain checksum of this string is used
    instead. Including the first beat keeps two chunks in the same scene from
    opening with the exact same camera sentence.
    """
    first = next((el.text for el in elements if el.kind in ("action", "dialogue")), "")
    return f"{context}|{first[:60]}"


def _seed(key: str) -> int:
    return sum(ord(c) for c in (key or ""))


def camera_sentence(shot_index: int, *, has_dialogue: bool, has_action: bool,
                    seed: str = "", avoid: frozenset[str] | set[str] = frozenset()) -> str:
    """Pick a camera-motion sentence appropriate to the shot's content.

    ``avoid`` (cameras already used in this chunk) is skipped when possible, so
    one prompt does not repeat the same movement in every shot.
    """
    if shot_index == 0 and not has_dialogue:
        pool = _ESTABLISH_CAMERAS
    elif has_dialogue:
        pool = _DIALOGUE_CAMERAS
    else:
        pool = _ACTION_CAMERAS
    start = (_seed(seed) + shot_index) % len(pool)
    for offset in range(len(pool)):
        candidate = pool[(start + offset) % len(pool)]
        if candidate not in avoid:
            return candidate
    return pool[start]


def cut_lead(shot_index: int, seed: str = "") -> str:
    """Opening clause for a later shot (before its camera sentence)."""
    return _CUT_LEADS[(_seed(seed) + shot_index) % len(_CUT_LEADS)]


def _join(items: list[str]) -> str:
    if len(items) == 1:
        return items[0]
    return ", ".join(items[:-1]) + " and " + items[-1]


def soundscape_sentences(chunk: dict) -> str:
    """Derive ``overall_soundscape`` from action beats, not verbatim action.

    Uses a conservative cue lexicon plus a location ambience line, so the field
    describes sounds (ambience + physical actions) and never repeats the action
    sentence, names a character, or includes dialogue.
    """
    cues: list[str] = []
    for element in chunk.get("elements", []):
        if element.kind != "action":
            continue
        low = element.text.lower()
        for pattern, phrase in _SOUND_CUES:
            if phrase not in cues and re.search(pattern, low):
                cues.append(phrase)
    sentences: list[str] = []
    if cues:
        sentences.append(f"Sounds of {_join(cues)} continue through the scene.")
    noun = scene_noun(chunk.get("context", ""))
    if noun:
        sentences.append(f"Low {noun} ambience continues underneath.")
    if not sentences:
        return "Quiet room tone with soft movement sounds."
    return " ".join(sentences[:2])


def music_line(chunk: dict) -> str:
    """``non_diegetic_music``: N/A unless the script explicitly features a score."""
    for element in chunk.get("elements", []):
        if element.kind == "action" and _MUSIC_HINTS.search(element.text):
            return "A continuous musical score at a slow tempo plays underneath."
    return "N/A"
