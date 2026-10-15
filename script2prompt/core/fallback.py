"""Rule-based template filler (offline fallback).

Deterministic prose from parsed elements: style sentence, context, action
sentences verbatim, dialogue verbatim inside ``<d>[English]...</d>`` with
stable speaker IDs from the bible, one camera sentence per shot, plus the
mode-specific frame anchors (Milestone 2: I2VA/FL2VA/L2VA).
The LLM rewrite (Milestone 4) will replace this prose, not the structure.
"""
from __future__ import annotations

import re

from script2prompt.parsers.base import Element

from .characters import Character, title
from .chunker import split_sentences
from .modes import instruction_line


def _clean(text: str) -> str:
    return re.sub(r"\s+", " ", text.strip())


def _finish(sentence: str) -> str:
    sentence = _clean(sentence)
    if sentence and sentence[-1] not in ".!?":
        sentence += "."
    return sentence


def _is_voiceover(extension: str, delivery: str) -> bool:
    blob = re.sub(r"[^A-Z]", "", f"{extension} {delivery}".upper())
    return "VOICEOVER" in blob or blob in ("OS", "VO", "OC")


def _speaker_head(name: str, char: Character | None, mentioned: set[str],
                  subject_labels: dict[str, str] | None = None) -> str:
    readable = title(name)
    sid = char.speaker_id if char and char.speaker_id else None
    label = (subject_labels or {}).get(name)
    if label:
        # Full-reference form (guide §5.4): <Subject N> (Sx) with an appositive
        # description on first mention, bare label afterwards.
        if name not in mentioned:
            mentioned.add(name)
            appositive = f", {readable}"
            if char and char.description:
                appositive += f", {char.description}"
            if sid:
                return f"{label} ({sid}){appositive}"
            return f"{label}{appositive}"
        return f"{label} ({sid})" if sid else label
    if char and char.description and name not in mentioned:
        mentioned.add(name)
        base = f"{readable}, {char.description}"
    else:
        base = readable
    return f"{base} ({sid})" if sid else base


def _render_dialogue(words: str, head: str, voiceover: bool, mark: str) -> str:
    # Plain form matches Example_Text2Video_Prompt.txt: no colon after "says",
    # no space after the language tag, terminal period outside </d>.
    # Voiceover keeps the guide's fixed phrase (with colon).
    tag = f"<d>[English]{_clean(words)}</d>."
    if voiceover:
        line = f"{head} says in an off-screen voiceover: {tag} {head}'s lips remain completely closed."
    else:
        line = f"{head} says {tag}"
    if mark in ("out", "both"):
        line += " <scenetrans> The line continues seamlessly across the cut."
    if mark in ("in", "both"):
        line = f"<scenetrans> The line carries over from the previous shot as {line}"
    return line


def _shot_text(elements: list[Element], speakers: dict[str, Character],
               mentioned: set[str], opening: str,
               subject_labels: dict[str, str] | None = None) -> str:
    parts = [opening] if opening else []
    cue: Element | None = None
    delivery = ""
    for el in elements:
        if el.kind == "character":
            cue = el
            delivery = ""
        elif el.kind == "parenthetical":
            delivery = el.text.strip().strip("()").strip()
        elif el.kind == "dialogue":
            name = cue.meta.get("name", "") if cue else ""
            ext = cue.meta.get("extension", "") if cue else ""
            char = speakers.get(name) if name else None
            head = _speaker_head(name, char, mentioned, subject_labels) if name else "An unseen speaker"
            parts.append(
                _render_dialogue(el.text, head, _is_voiceover(ext, delivery), el.meta.get("scenetrans", ""))
            )
            delivery = ""
        elif el.kind == "action":
            parts.extend(_finish(s) for s in split_sentences(el.text))
    return " ".join(parts)


def _first_opening(mode: str, context: str) -> str:
    """Opening sentences for [Shot 1] per mode (guide §3 structures)."""
    base = "A medium-wide shot frames the scene."
    if mode == "I2VA":
        anchor = "The subject shown in <Picture 1> holds the composition, preserving appearance, clothing, and positioning"
        anchor += f" in {context}" if context else ""
        anchor += "."
        return f"{base} {anchor} The camera pushes in with small amplitude at slow speed."
    if mode == "FL2VA":
        return (
            f"{base} The subject begins in the position and framing established by "
            "Picture 1. The camera holds a static shot."
        )
    if mode == "L2VA":
        return (
            f"{base} The scene opens on a plausible preceding state, before the "
            "moment shown in <Picture 1>. The camera pushes in with small amplitude at slow speed."
        )
    opening = base
    if context:
        opening += f" The scene takes place at {context}."
    return opening + " The camera pushes in with small amplitude at slow speed."


def _closing(mode: str) -> str:
    """Final landing sentence for single-path keyframe modes."""
    if mode == "FL2VA":
        return (
            "The action settles into the pose, spacing, and composition "
            "established by Picture 2 at the end of the shot."
        )
    if mode == "L2VA":
        return (
            "The scene converges on the exact composition established by "
            "<Picture 1> at the end of the shot."
        )
    return ""


def build(chunk: dict, bible: list[Character] = (), mode: str = "T2VA",
          style: str = "Live-action, cinematic") -> str:
    """Build a deterministic prompt for a chunk (T2VA/I2VA/FL2VA/L2VA)."""
    if mode not in ("T2VA", "I2VA", "FL2VA", "L2VA"):
        raise NotImplementedError(f"{mode} builder arrives in Milestone 3")
    speakers = chunk.get("speakers", {})
    context = _clean(chunk.get("context", ""))
    shots = chunk.get("shots", [])
    duration = chunk.get("duration", 8.0)
    mentioned: set[str] = set()
    rendered: list[str] = []
    for i, shot in enumerate(shots):
        if i == 0:
            # Style lives in its own opening sentence (per the real example),
            # not inline in [Shot 1].
            opening = _first_opening(mode, context)
        else:
            opening = (
                f"[Shot {i + 1}] At {shot['start']}, the camera cuts to a new "
                "angle on the ongoing action. The camera holds a static shot."
            )
        body = _shot_text(shot["elements"], speakers, mentioned, opening)
        closing = _closing(mode)
        if closing and i == len(shots) - 1:
            body = f"{body} {closing}"
        rendered.append(body)
    style_sentence = _finish(style)
    description = f"{style_sentence}\n[Shot 1] {rendered[0]}" if rendered else f"{style_sentence}\n[Shot 1] ..."
    for extra in rendered[1:]:
        description += f"\n{extra}"

    actions = [e.text for e in chunk.get("elements", []) if e.kind == "action"]
    sentences: list[str] = []
    for action in actions:
        sentences.extend(_finish(s) for s in split_sentences(action))
        if len(sentences) >= 2:
            break
    sentences = sentences[:2]
    if not sentences:
        sentences = ["Quiet room tone with soft movement sounds."]
    elif len(sentences) < 2:
        sentences.append("Soft room tone continues underneath.")

    fields = (
        f"integrated_multimodal_description:\n{description}\n\n"
        f"overall_soundscape:\n{' '.join(sentences)}\n\n"
        "non_diegetic_music:\nN/A"
    )
    # Field labels on their own lines, matching Example_*_Prompt.txt layout.
    instruction = instruction_line(mode, final_shot=max(len(shots), 1), duration=duration)
    return f"{instruction}\n\n{fields}" if instruction else fields
