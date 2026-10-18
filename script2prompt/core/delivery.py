"""Delivery tags that may appear inside ``<d>...</d>`` dialogue.

These tags express nuance (pauses, emphasis, non-verbal sounds) and are a
**community finding**, not part of MiniMax's published H3 guide. They have been
observed to work in practice, so the deterministic builders insert them when a
screenplay parenthetical clearly cues a delivery, and the LLM prompts are told
to use them when the script supplies the cue.

Reference table: ``docs/H3_Prompting_Docs/Dialogue_Delivery_Tags.md``.
Placement: a leading tag goes right after the language tag, e.g.
``<d>[English]<inhale> Alright, let's do this.</d>``; a wrapping tag encloses the
affected words, e.g. ``<d>[English]I will <i>not</i> tolerate this.</d>``.
"""
from __future__ import annotations

import re

# (group, tag, what, example, wrapped)
DELIVERY_TAGS: tuple[dict[str, object], ...] = (
    {"group": "Pauses and breath", "tag": "<pause>", "what": "Short pause",
     "ex": "Okay, so. <pause> This is just me talking.", "wrap": False},
    {"group": "Pauses and breath", "tag": "<long pause>", "what": "Longer pause",
     "ex": "I mean <long pause> I don't even know.", "wrap": False},
    {"group": "Pauses and breath", "tag": "<breath>", "what": "Breathing sound",
     "ex": "And then <breath> it just happened.", "wrap": False},
    {"group": "Pauses and breath", "tag": "<inhale>", "what": "In breath",
     "ex": "<inhale> Alright, let's do this.", "wrap": False},
    {"group": "Pauses and breath", "tag": "<exhale>", "what": "Out breath",
     "ex": "<exhale> Fine. Have it your way.", "wrap": False},
    {"group": "Pauses and breath", "tag": "<catches breath>", "what": "Out of breath",
     "ex": "Wait <catches breath> hold on a sec.", "wrap": False},
    {"group": "Pauses and breath", "tag": "<deep breath>", "what": "Calming down",
     "ex": "<deep breath> Okay. I can do this.", "wrap": False},
    {"group": "Delivery and emphasis", "tag": "<i>", "what": "Emphasize 1-4 words",
     "ex": "I was <i>not</i> expecting that.", "wrap": True},
    {"group": "Delivery and emphasis", "tag": "<whisper>", "what": "Whisper delivery",
     "ex": "<whisper> Don't tell anyone this.</whisper>", "wrap": True},
    {"group": "Delivery and emphasis", "tag": "<softer>", "what": "Quieter delivery",
     "ex": "<softer> I don't think I can say it.", "wrap": False},
    {"group": "Delivery and emphasis", "tag": "<humming>", "what": "Humming a tune",
     "ex": "<humming> da-da-da-beautiful-day.</humming>", "wrap": True},
    {"group": "Delivery and emphasis", "tag": "<stutter>", "what": "Stutters the words",
     "ex": "<stutter> I ca can't believe that.", "wrap": False},
    {"group": "Delivery and emphasis", "tag": "<uh>", "what": "Filler / hesitation",
     "ex": "So, like <uh> what was I saying?", "wrap": False},
    {"group": "Non-verbal sounds", "tag": "<laughs>", "what": "Laughing",
     "ex": "That's <laughs> that's actually funny.", "wrap": False},
    {"group": "Non-verbal sounds", "tag": "<chuckle>", "what": "Small laugh",
     "ex": "<chuckle> You're not serious.", "wrap": False},
    {"group": "Non-verbal sounds", "tag": "<sighs>", "what": "Sigh",
     "ex": "<sighs> I really tried.", "wrap": False},
    {"group": "Non-verbal sounds", "tag": "<gasp>", "what": "Sharp intake",
     "ex": "<gasp> Oh my God.", "wrap": False},
    {"group": "Non-verbal sounds", "tag": "<coughs>", "what": "Cough",
     "ex": "<coughs> Sorry, one sec.", "wrap": False},
    {"group": "Non-verbal sounds", "tag": "<clears throat>", "what": "Throat clear",
     "ex": "<clears throat> So anyway", "wrap": False},
    {"group": "Non-verbal sounds", "tag": "<sniff>", "what": "Sniffing",
     "ex": "<sniff> It's just really sad.", "wrap": False},
    {"group": "Non-verbal sounds", "tag": "<mhm>", "what": "Agreement sound",
     "ex": "Yeah, <mhm> exactly.", "wrap": False},
    {"group": "Non-verbal sounds", "tag": "<phew>", "what": "Relief",
     "ex": "<phew> That was close.", "wrap": False},
)

WRAP_TAGS = frozenset(str(t["tag"]) for t in DELIVERY_TAGS if t["wrap"])
ALL_TAGS = tuple(str(t["tag"]) for t in DELIVERY_TAGS)

# Screenplay parenthetical (normalized) -> delivery tag. Only unambiguous
# delivery/sound cues are listed; anything else (V.O., CONT'D, "to Will",
# "(closer)") is left untagged rather than guessed at.
_PARENTHETICAL_TAGS: dict[str, str] = {
    "beat": "<pause>",
    "pause": "<pause>",
    "pauses": "<pause>",
    "long pause": "<long pause>",
    "breath": "<breath>",
    "breathless": "<catches breath>",
    "out of breath": "<catches breath>",
    "panting": "<catches breath>",
    "deep breath": "<deep breath>",
    "inhale": "<inhale>",
    "inhales": "<inhale>",
    "exhale": "<exhale>",
    "exhales": "<exhale>",
    "whisper": "<whisper>",
    "whispers": "<whisper>",
    "whispering": "<whisper>",
    "softly": "<softer>",
    "quietly": "<softer>",
    "under breath": "<softer>",
    "hums": "<humming>",
    "humming": "<humming>",
    "stutter": "<stutter>",
    "stutters": "<stutter>",
    "stammering": "<stutter>",
    "laughs": "<laughs>",
    "laughing": "<laughs>",
    "chuckle": "<chuckle>",
    "chuckles": "<chuckle>",
    "chuckling": "<chuckle>",
    "sighs": "<sighs>",
    "sighing": "<sighs>",
    "gasp": "<gasp>",
    "gasps": "<gasp>",
    "coughs": "<coughs>",
    "coughing": "<coughs>",
    "clears throat": "<clears throat>",
    "clearing throat": "<clears throat>",
    "sniff": "<sniff>",
    "sniffs": "<sniff>",
    "sniffles": "<sniff>",
    "uh": "<uh>",
    "hesitates": "<uh>",
    "hesitant": "<uh>",
    "phew": "<phew>",
    "mhm": "<mhm>",
}

# Longest phrases first so "long pause"/"under breath" beat their substrings.
_PHRASES = sorted(_PARENTHETICAL_TAGS, key=len, reverse=True)


def tag_for(parenthetical: str) -> tuple[str, bool] | None:
    """Map a screenplay parenthetical to ``(tag, wrapped)``, or ``None``.

    An exact normalized match wins; otherwise the longest known phrase contained
    in the parenthetical is used (``"a long pause"`` -> ``<long pause>``).
    """
    key = re.sub(r"[^a-z ]", " ", parenthetical.lower())
    key = re.sub(r"\s+", " ", key).strip()
    if not key:
        return None
    tag = _PARENTHETICAL_TAGS.get(key)
    if tag is None:
        for phrase in _PHRASES:
            if re.search(rf"\b{re.escape(phrase)}\b", key):
                tag = _PARENTHETICAL_TAGS[phrase]
                break
    if tag is None:
        return None
    return tag, tag in WRAP_TAGS


def apply_tags(words: str, parenthetical: str) -> str:
    """Insert a cued delivery tag into a verbatim dialogue line.

    A leading tag is placed before the words (``<softer> I don't...``); a
    wrapping tag encloses the whole line (``<whisper> ... </whisper>``). Returns
    the words unchanged when the parenthetical cues no known delivery.
    """
    found = tag_for(parenthetical)
    if found is None:
        return words
    tag, wrapped = found
    if wrapped:
        return f"{tag}{words}</{tag[1:]}"
    return f"{tag} {words}"
