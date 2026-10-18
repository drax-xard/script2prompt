"""Chunker: pack scene beats into <=10s, <=3-shot chunks.

Duration estimate per docs/PROJECT_PLAN.md §4:
``action_words / 2.5 * 0.4 + dialogue_words / 2.75 + 1.0s overhead``.
Dialogue that overruns the 10s cap is pre-split at sentence boundaries (<=18
words per piece) with ``scenetrans`` markers for the builder. The overrun is
measured per cue **cumulatively**: a single long line is split, and so is a run
of short lines that together exceed ``MONOLOGUE_WORDS`` (a monologue written one
line per beat, or hard-wrapped PDF text).

A dialogue cue and its lines stay in one atomic block so a character is never
separated from what they say; whenever a monologue is split, the cue is
re-emitted before each continuation piece so the speaker survives the chunk
boundary.
"""
from __future__ import annotations

import re

from script2prompt.parsers.base import Element

from .characters import Character, split_joint

CAP_SECONDS = 10.0
MIN_SECONDS = 5.0
DIALOGUE_WPS = 2.75
ACTION_WPS = 0.16
PIECE_WORDS = 18
# Longest monologue that still fits the 10s cap after the 1.0s overhead.
MONOLOGUE_WORDS = int((CAP_SECONDS - 1.0) * DIALOGUE_WPS)
# Longest action beat that still fits the 10s cap after the 1.0s overhead.
ACTION_WORDS = int((CAP_SECONDS - 1.0) / ACTION_WPS)
# Action pieces are denser than dialogue, so split to roughly half the cap.
ACTION_PIECE_WORDS = max(ACTION_WORDS // 2, PIECE_WORDS)


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
    return action * ACTION_WPS + dialogue / DIALOGUE_WPS + 1.0


def _pieces(text: str, piece_words: int) -> list[str]:
    """Split ``text`` at sentence boundaries into <=``piece_words`` pieces.

    Sentences that individually exceed the budget are hard-split on word count.
    """
    units: list[str] = []
    for sentence in split_sentences(text):
        if count_words(sentence) <= piece_words:
            units.append(sentence)
        else:
            words = sentence.split()
            units.extend(
                " ".join(words[i : i + piece_words]) for i in range(0, len(words), piece_words)
            )
    pieces: list[str] = []
    current = ""
    for unit in units:
        candidate = f"{current} {unit}".strip()
        if current and count_words(candidate) > piece_words:
            pieces.append(current)
            current = unit
        else:
            current = candidate
    if current:
        pieces.append(current)
    return pieces


def _split_long_dialogue(elements: list[Element]) -> list[Element]:
    """Split dialogue so no run under one cue exceeds ``MONOLOGUE_WORDS``.

    Words are counted per cue, not per line: several short lines that together
    overflow the cap (a monologue written one line per beat, or hard-wrapped PDF
    text) are broken just like a single long line. The active cue is re-emitted
    before each continuation piece and crossing pieces carry ``scenetrans``
    markers so the speaker is not lost and the cut is described.
    """
    out: list[Element] = []
    cue: Element | None = None
    consumed = 0

    def mid_run() -> bool:
        # We are part-way through a cue's speech if the last thing emitted was
        # that cue's own dialogue/parenthetical (so a new piece needs its own
        # cue to stay attached to the speaker).
        return bool(out) and out[-1].kind in ("dialogue", "parenthetical")

    def emit_cue() -> None:
        if cue is not None:
            out.append(Element("character", cue.text, dict(cue.meta)))

    def mark_last(mark: str) -> None:
        for el in reversed(out):
            if el.kind == "dialogue":
                current = el.meta.get("scenetrans", "")
                if not current:
                    el.meta["scenetrans"] = mark
                elif current != mark:
                    el.meta["scenetrans"] = "both"
                return

    def add_piece(text: str, meta: dict, carries: bool, continues: bool) -> None:
        mark = "both" if (carries and continues) else "in" if carries else "out" if continues else ""
        piece_meta = dict(meta)
        if mark:
            piece_meta["scenetrans"] = mark
        out.append(Element("dialogue", text, piece_meta))

    for el in elements:
        if el.kind == "character":
            cue = el
            consumed = 0
            out.append(el)
            continue
        if el.kind != "dialogue":
            out.append(el)
            continue
        words = count_words(el.text)
        if words > MONOLOGUE_WORDS:
            # A single over-long line: split it into sentence-boundary pieces.
            pieces = _pieces(el.text, PIECE_WORDS)
            total = len(pieces)
            for i, piece in enumerate(pieces):
                starts_new = i > 0 or mid_run()
                if starts_new:
                    if i == 0:
                        mark_last("out")
                    emit_cue()
                add_piece(piece, el.meta, carries=starts_new, continues=i < total - 1)
            # The final piece keeps the run going, so later short lines are
            # still measured against the cap cumulatively.
            consumed = count_words(pieces[-1]) if pieces else 0
            continue
        if cue is not None and consumed and consumed + words > MONOLOGUE_WORDS:
            # Short lines that overflow together: break, re-emit the cue, and
            # flag the crossing on both sides.
            mark_last("out")
            emit_cue()
            add_piece(el.text, el.meta, carries=True, continues=False)
            consumed = words
            continue
        out.append(el)
        consumed += words
    return out


def _split_long_action(elements: list[Element]) -> list[Element]:
    """Split action beats longer than the 10s cap into sentence-boundary pieces.

    Without this a long action line is clamped to a single 10s chunk, silently
    exceeding the speech/action budget. Pieces share the chunk's 1.0s overhead,
    so a piece target of half the cap keeps two pieces inside one chunk.
    """
    out: list[Element] = []
    for el in elements:
        if el.kind != "action" or count_words(el.text) <= ACTION_WORDS:
            out.append(el)
            continue
        for piece in _pieces(el.text, ACTION_PIECE_WORDS):
            out.append(Element("action", piece, dict(el.meta)))
    return out


def _blocks(elements: list[Element]) -> list[list[Element]]:
    """Group elements so a character cue stays with its lines.

    Each block is atomic for packing: a cue starts a block that absorbs the
    following parentheticals/dialogue, so a cue is never flushed alone.
    """
    blocks: list[list[Element]] = []
    current: list[Element] | None = None
    for el in elements:
        if el.kind == "character":
            current = [el]
            blocks.append(current)
        elif el.kind in ("parenthetical", "dialogue") and current is not None:
            current.append(el)
        else:
            blocks.append([el])
            current = None
    return blocks


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
            raw = el.meta.get("name", "")
            for name in split_joint(raw) or ([raw] if raw else []):
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
          shots_max: int = 3, mode: str = "T2VA") -> list[dict]:
    """Split a scene into duration-capped chunks (greedy pack on estimate).

    FL2VA favors a single shot per chunk (guide §3.2), so shot breaks are
    disabled for that mode.
    """
    by_name = {c.name: c for c in bible}
    effective_shots = 1 if mode == "FL2VA" else shots_max
    elements = _split_long_dialogue(scene.get("elements", []))
    elements = _split_long_action(elements)
    packed: list[list[Element]] = []
    current: list[Element] = []

    def flush() -> None:
        if current:
            packed.append(list(current))
            current.clear()

    for block in _blocks(elements):
        if current and estimate(current + block) > duration:
            flush()
        current.extend(block)
    flush()

    # A sub-5s trailing pack is merged into its predecessor when the pair still
    # fits the 10s cap, so a one-line tail is not padded to a full 5s chunk.
    while len(packed) >= 2 and estimate(packed[-1]) < MIN_SECONDS:
        if estimate(packed[-2] + packed[-1]) <= CAP_SECONDS:
            packed[-2].extend(packed.pop())
        else:
            break

    return [_make_chunk(scene, block, by_name, duration, effective_shots) for block in packed]
