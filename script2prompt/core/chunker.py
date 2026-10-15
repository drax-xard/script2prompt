"""Chunker: pack scene beats into <=10s, <=3-shot chunks.

Duration estimate per PROJECT_PLAN.md §4:
``action_words / 2.5 * 0.4 + dialogue_words / 2.75 + 1.0s overhead``.
Single dialogue lines over 30 words are pre-split at sentence boundaries
(<=18 words per piece) with ``scenetrans`` markers for the builder.
"""
from __future__ import annotations

import re

from script2prompt.parsers.base import Element

from .characters import Character

CAP_SECONDS = 10.0
MIN_SECONDS = 5.0
MONOLOGUE_WORDS = 30
PIECE_WORDS = 18


def count_words(text: str) -> int:
    """Count whitespace-separated words."""
    return len(text.split())


def split_sentences(text: str) -> list[str]:
    """Split text into sentences on . ! ? boundaries."""
    return [p.strip() for p in re.split(r"(?<=[.!?])\s+", text.strip()) if p.strip()]


def fmt_stamp(seconds: float) -> str:
    """Format seconds as MM:SS.mmm cut timestamp."""
    return f"{int(seconds // 60):02d}:{seconds % 60:06.3f}"


def estimate(elements: list[Element]) -> float:
    """Estimate playback seconds for a list of elements."""
    action = sum(count_words(e.text) for e in elements if e.kind == "action")
    dialogue = sum(count_words(e.text) for e in elements if e.kind == "dialogue")
    return action * 0.16 + dialogue / 2.75 + 1.0


def _split_long_dialogue(elements: list[Element]) -> list[Element]:
    """Split >30-word dialogue lines into <=18-word pieces with markers."""
    out: list[Element] = []
    for el in elements:
        if el.kind != "dialogue" or count_words(el.text) <= MONOLOGUE_WORDS:
            out.append(el)
            continue
        pieces: list[str] = []
        current = ""
        for sentence in split_sentences(el.text):
            candidate = f"{current} {sentence}".strip()
            if current and count_words(candidate) > PIECE_WORDS:
                pieces.append(current)
                current = sentence
            else:
                current = candidate
        if current:
            pieces.append(current)
        if len(pieces) <= 1:  # no sentence breaks: hard-split on words
            words = el.text.split()
            pieces = [" ".join(words[i : i + PIECE_WORDS]) for i in range(0, len(words), PIECE_WORDS)]
        total = len(pieces)
        for i, piece in enumerate(pieces):
            if total == 1:
                mark = ""
            elif i == 0:
                mark = "out"
            elif i == total - 1:
                mark = "in"
            else:
                mark = "both"
            meta = dict(el.meta)
            meta["scenetrans"] = mark
            out.append(Element("dialogue", piece, meta))
    return out


def _make_chunk(scene: dict, elements: list[Element], by_name: dict[str, Character],
                duration: float, shots_max: int) -> dict:
    est = estimate(elements)
    clamped = min(max(est, MIN_SECONDS), CAP_SECONDS)
    groups: list[list[Element]] = [[]]
    for el in elements:
        if el.kind == "character" and groups[-1] and len(groups) < shots_max:
            groups.append([])
        groups[-1].append(el)
    count = len(groups)
    shots = [{"elements": group, "start": fmt_stamp(clamped * i / count)} for i, group in enumerate(groups)]
    speakers: dict[str, Character] = {}
    for el in elements:
        if el.kind == "character":
            name = el.meta.get("name", "")
            if name and name not in speakers:
                speakers[name] = by_name.get(name, Character(name, None, ""))
    return {
        "context": scene.get("context", ""),
        "elements": elements,
        "duration": round(clamped, 3),
        "shots": shots,
        "speakers": speakers,
    }


def chunk(scene: dict, bible: list[Character] = (), duration: float = 8.0,
          shots_max: int = 3) -> list[dict]:
    """Split a scene into duration-capped chunks (greedy pack on estimate)."""
    by_name = {c.name: c for c in bible}
    elements = _split_long_dialogue(scene.get("elements", []))
    chunks: list[dict] = []
    current: list[Element] = []

    def flush() -> None:
        if current:
            chunks.append(_make_chunk(scene, list(current), by_name, duration, shots_max))
            current.clear()

    for el in elements:
        if current and estimate(current + [el]) > duration:
            flush()
        current.append(el)
    flush()
    return chunks
