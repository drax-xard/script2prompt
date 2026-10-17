"""R2V full-reference 6-section builder (Milestone 3, rule-based template).

Section order and markers follow the reference guide and
``Example_Reference_Prompt.txt``: subject_definitions, summary (+ task-type
prefix), retention_analysis (no speaker IDs inside, guide §5.4),
detailed_description (style sentence(s) before [Shot 1]), overall_soundscape,
non_diegetic_music. Shot prose reuses the fallback renderer with
``<Subject N> (Sx)`` speaker heads. Reference slots come from
``ref_manifest.propose`` (placeholders the user fulfills externally).
"""
from __future__ import annotations

from . import fallback
from .characters import Character, title
from .ref_manifest import propose
from .render import clean, soundscape_sentences


def _definitions(manifest: dict) -> list[str]:
    lines = []
    for sub in manifest["subjects"]:
        if sub["kind"] == "environment":
            when = f" at {sub['description'].lower()}" if sub.get("description") else ""
            lines.append(
                f"{sub['label']} is the {sub['name']} environment{when}, with the layout "
                "and atmosphere established in [Shot 1]."
            )
        elif sub["speaker_id"]:
            desc = f", {sub['description']}" if sub["description"] else ""
            lines.append(
                f"{sub['label']} is {title(sub['name'])}{desc}, "
                f"the speaker ({sub['speaker_id']}) defined by the script."
            )
        else:
            desc = f", {sub['description']}" if sub["description"] else ""
            lines.append(
                f"{sub['label']} is {title(sub['name'])}{desc}, "
                "a non-speaking character defined by the script."
            )
    for audio in manifest["audios"]:
        lines.append(
            f"{audio['label']} is the voice-timbre reference for "
            f"{audio['subject']} ({audio['speaker_id']}), containing a spoken "
            f"{audio['language']} vocal layer."
        )
    return lines


def _summary(manifest: dict, shots: int) -> str:
    prefix = " + ".join(manifest["task_types"])
    chars = [s for s in manifest["subjects"] if s["kind"] == "character"]
    envs = [s for s in manifest["subjects"] if s["kind"] == "environment"]
    if chars:
        cast = ", ".join(f"{s['label']} ({title(s['name'])})" for s in chars)
    else:
        cast = "the scripted characters"
    place = f" in {envs[0]['label']}" if envs else ""
    voices = " with the scripted dialogue performed in the referenced voices" if manifest["audios"] else ""
    plural = "s" if shots != 1 else ""
    return f"[{prefix}] The target video shows {cast}{place}, in {shots} shot{plural}{voices}."


def _retention(manifest: dict) -> list[str]:
    lines = []
    for sub in manifest["subjects"]:
        if sub["kind"] == "environment":
            kept = f"the {sub['name']} environment, layout, and atmosphere are retained"
        else:
            kept = f"{title(sub['name'])}'s identity"
            if sub["description"]:
                kept += f", {sub['description']}, is retained"
            else:
                kept += " is retained"
        lines.append(f"{sub['label']} ({sub['shots_text']}): fully_preserved - {kept}.")
    for audio in manifest["audios"]:
        lines.append(
            f"{audio['label']}: reference - its vocal timbre guides the dialogue "
            f"delivery of {audio['subject']} without copying the original signal."
        )
    return lines


def build(chunk: dict, bible: list[Character] = (), manifest: dict | None = None,
          style: str = "Live-action, cinematic") -> str:
    """Build a deterministic R2V prompt for a chunk."""
    manifest = manifest or propose(chunk, bible)
    speakers = chunk.get("speakers", {})
    shots = chunk.get("shots", [])
    subject_labels = {s["name"]: s["label"] for s in manifest["subjects"] if s["kind"] == "character"}

    mentioned: set[str] = set()
    rendered = []
    for i, shot in enumerate(shots):
        if i == 0:
            opening = (
                "The scene opens on the scripted location with the referenced "
                "subjects in place. The camera holds a static shot."
            )
        else:
            opening = (
                f"[Shot {i + 1}] At {shot['start']}, the camera cuts to a new "
                "angle on the ongoing action. The camera holds a static shot."
            )
        rendered.append(fallback._shot_text(shot["elements"], speakers, mentioned, opening, subject_labels))
    style = clean(style) or "Live-action, cinematic"
    style_line = f"The target video uses a {style[:1].lower() + style[1:]} style, matching the scripted scene."
    description = f"{style_line}\n\n[Shot 1] {rendered[0]}" if rendered else f"{style_line}\n\n[Shot 1] ..."
    for extra in rendered[1:]:
        description += f"\n{extra}"

    soundscape = soundscape_sentences(chunk)

    sections = [
        ("subject_definitions:", _definitions(manifest)),
        ("summary:", [_summary(manifest, max(len(shots), 1))]),
        ("retention_analysis:", _retention(manifest)),
        ("detailed_description:", [description]),
        ("overall_soundscape:", [soundscape]),
        ("non_diegetic_music:", ["N/A"]),
    ]
    return "\n\n".join(f"{label}\n" + "\n".join(lines) for label, lines in sections)
