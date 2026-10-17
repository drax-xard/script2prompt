"""Shared prose helpers for the deterministic prompt builders.

Both the base-mode builder (``fallback``) and the full-reference builder
(``r2v``) render the same way, so the small text utilities and the
``overall_soundscape`` derivation live here once.
"""
from __future__ import annotations

import re

from .chunker import split_sentences

__all__ = ["clean", "finish", "soundscape_sentences"]


def clean(text: str) -> str:
    """Collapse internal whitespace and strip the ends."""
    return re.sub(r"\s+", " ", text.strip())


def finish(sentence: str) -> str:
    """Clean a sentence and guarantee terminal punctuation."""
    sentence = clean(sentence)
    if sentence and sentence[-1] not in ".!?":
        sentence += "."
    return sentence


def soundscape_sentences(chunk: dict) -> str:
    """Derive ``overall_soundscape`` from the chunk's action beats.

    Uses the first two action sentences (1-4 sentence field budget) and always
    returns a non-empty string; never includes dialogue.
    """
    actions = [e.text for e in chunk.get("elements", []) if e.kind == "action"]
    sentences: list[str] = []
    for action in actions:
        sentences.extend(finish(s) for s in split_sentences(action))
        if len(sentences) >= 2:
            break
    sentences = sentences[:2]
    if not sentences:
        return "Quiet room tone with soft movement sounds."
    if len(sentences) < 2:
        sentences.append("Soft room tone continues underneath.")
    return " ".join(sentences)
