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

from .characters import Character, split_joint, title
from .chunker import split_sentences
from .delivery import apply_tags
from .modes import instruction_line
from .render import (
    camera_sentence,
    clean,
    cut_lead,
    finish,
    music_line,
    scene_phrase,
    seed_key,
    soundscape_sentences,
)


def _is_voiceover(extension: str, delivery: str) -> bool:
    """True only for a real voiceover (V.O.), not off-screen (O.S./O.C.).

    The extension and delivery are checked independently, and each
    parenthetical is normalized on its own, so ``(V.O.)`` combined with an extra
    marker (``MARA (V.O.) (CONT'D)``) is still a voiceover, while ``(O.S.)`` is
    left as an on-screen-but-unseen speaker rather than a closed-lips one.
    """
    tokens = set()
    for parenthetical in (extension, delivery):
        tokens.update(re.findall(r"\(([^)]*)\)", parenthetical))
        tokens.add(parenthetical)
    normalized = {re.sub(r"[^A-Z]", "", token.upper()) for token in tokens}
    return bool(normalized & {"VO", "VOICEOVER"})


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


def _joint_head(names: list[str], speakers: dict[str, Character], mentioned: set[str],
                subject_labels: dict[str, str] | None = None) -> str:
    """Compound speaker head for a joint cue, e.g. ``Elena and Mara (S1,S2)``."""
    chars = [speakers.get(name) for name in names]
    ids = [c.speaker_id for c in chars if c and c.speaker_id]
    labels = [(subject_labels or {}).get(name) for name in names]
    first = [name for name in names if name not in mentioned]
    if subject_labels and all(labels):
        head = " and ".join(labels)
        if first:
            head += f", {' and '.join(title(name) for name in names)}"
    else:
        parts = []
        for name in names:
            char = speakers.get(name)
            if name in first and char and char.description:
                parts.append(f"{title(name)}, {char.description}")
            else:
                parts.append(title(name))
        head = " and ".join(parts)
    for name in names:
        mentioned.add(name)
    return f"{head} ({','.join(ids)})" if ids else head


def _render_dialogue(words: str, head: str, voiceover: bool, mark: str,
                     plural: bool = False, delivery: str = "") -> str:
    # Plain form matches Example_Text2Video_Prompt.txt: no colon after "says",
    # no space after the language tag, terminal period outside </d>.
    # Voiceover keeps the guide's fixed phrase (with colon). A parenthetical
    # that cues delivery contributes a community tag inside <d>.
    body = clean(words)
    if delivery:
        body = apply_tags(body, delivery)
    tag = f"<d>[English]{body}</d>."
    if voiceover:
        line = f"{head} says in an off-screen voiceover: {tag} {head}'s lips remain completely closed."
    else:
        line = f"{head} {'say' if plural else 'says'} {tag}"
    if mark in ("out", "both"):
        line += " <scenetrans> The line continues seamlessly across the cut."
    if mark in ("in", "both"):
        line = f"<scenetrans> The line carries over from the previous shot as {line}"
    return line


def _strip_intro_traits(text: str, speakers: dict[str, Character]) -> str:
    """Drop a ``(traits)`` parenthetical that merely repeats the speaker's bio.

    ``ELENA (40s, sharp editor) stands…`` reads redundantly once the speaker head
    already carries her description; the parenthetical is removed only when it
    matches the bible entry verbatim.
    """
    for name, char in speakers.items():
        if not char or not char.description:
            continue
        pattern = re.compile(
            re.escape(name) + r"\s*\(" + re.escape(char.description) + r"\)", re.IGNORECASE
        )
        text = pattern.sub(name, text)
    return text


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
            raw = cue.meta.get("name", "") if cue else ""
            ext = cue.meta.get("extension", "") if cue else ""
            joint = split_joint(raw)
            if len(joint) > 1:
                head = _joint_head(joint, speakers, mentioned, subject_labels)
            elif raw:
                head = _speaker_head(raw, speakers.get(raw), mentioned, subject_labels)
            else:
                head = "An unseen speaker"
            parts.append(
                _render_dialogue(
                    el.text, head, _is_voiceover(ext, delivery),
                    el.meta.get("scenetrans", ""), plural=len(joint) > 1,
                    delivery=delivery,
                )
            )
            delivery = ""
        elif el.kind == "action":
            parts.extend(finish(s) for s in split_sentences(_strip_intro_traits(el.text, speakers)))
    return " ".join(parts)


def _first_opening(mode: str, context: str, has_dialogue: bool, has_action: bool,
                   seed: str = "", used_cameras: set[str] | None = None) -> str:
    """Opening sentences for [Shot 1] per mode (guide §3 structures)."""
    phrase = scene_phrase(context)
    base = (
        f"A medium-wide shot establishes {phrase}."
        if phrase
        else "A medium-wide shot frames the scene."
    )
    camera = camera_sentence(
        0, has_dialogue=has_dialogue, has_action=has_action, seed=seed,
        avoid=used_cameras or frozenset(),
    )
    if used_cameras is not None:
        used_cameras.add(camera)
    if mode == "I2VA":
        anchor = (
            "The subject shown in <Picture 1> holds the composition, preserving "
            "appearance, clothing, and positioning"
        )
        anchor += f" in {phrase}" if phrase else ""
        return f"{base} {anchor}. {camera}"
    if mode == "FL2VA":
        static = "The camera holds a static shot."
        if used_cameras is not None:
            used_cameras.add(static)
        return (
            f"{base} The subject begins in the position and framing established by "
            f"Picture 1. {static}"
        )
    if mode == "L2VA":
        return (
            f"{base} The scene opens on a plausible preceding state, before the "
            f"moment shown in <Picture 1>. {camera}"
        )
    return f"{base} {camera}"


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
        raise NotImplementedError(
            f"fallback.build handles T2VA/I2VA/FL2VA/L2VA only; "
            f"{mode} is built by core.r2v.build"
        )
    speakers = chunk.get("speakers", {})
    context = clean(chunk.get("context", ""))
    shots = chunk.get("shots", [])
    duration = chunk.get("duration", 8.0)
    mentioned: set[str] = set()
    rendered: list[str] = []
    used_cameras: set[str] = set()
    for i, shot in enumerate(shots):
        has_dialogue = any(el.kind == "dialogue" for el in shot["elements"])
        has_action = any(el.kind == "action" for el in shot["elements"])
        seed = seed_key(context, shot["elements"])
        if i == 0:
            # Style lives in its own opening sentence (per the real example),
            # not inline in [Shot 1].
            opening = _first_opening(mode, context, has_dialogue, has_action, seed, used_cameras)
        else:
            camera = camera_sentence(
                i, has_dialogue=has_dialogue, has_action=has_action, seed=seed,
                avoid=used_cameras,
            )
            used_cameras.add(camera)
            opening = f"[Shot {i + 1}] At {shot['start']}, {cut_lead(i, seed)}. {camera}"
        body = _shot_text(shot["elements"], speakers, mentioned, opening)
        closing = _closing(mode)
        if closing and i == len(shots) - 1:
            body = f"{body} {closing}"
        rendered.append(body)
    style_sentence = finish(style)
    description = f"{style_sentence}\n[Shot 1] {rendered[0]}" if rendered else f"{style_sentence}\n[Shot 1] ..."
    for extra in rendered[1:]:
        description += f"\n{extra}"

    soundscape = soundscape_sentences(chunk)
    music = music_line(chunk)

    fields = (
        f"integrated_multimodal_description:\n{description}\n\n"
        f"overall_soundscape:\n{soundscape}\n\n"
        f"non_diegetic_music:\n{music}"
    )
    # Field labels on their own lines, matching Example_*_Prompt.txt layout.
    instruction = instruction_line(mode, final_shot=max(len(shots), 1), duration=duration)
    return f"{instruction}\n\n{fields}" if instruction else fields
