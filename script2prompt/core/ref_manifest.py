"""Reference-manifest proposer for R2V full-reference mode (Milestone 3).

v1: no image/video upload — the tool proposes Subject/Audio slots as
placeholders with a user checklist fulfilled externally. Identity-only
references stay inside ``<Subject N>`` definitions (guide §2.2): no
standalone ``<Picture N>`` entries are proposed without frame anchors,
so ``pictures``/``videos`` stay empty until the user attaches assets.
"""
from __future__ import annotations

from .characters import Character, title

TIMBRE_ROLE = "voice-timbre reference"


def _subject_shots(chunk: dict, name: str | None) -> list[int]:
    """1-based shot numbers where a subject appears (environment: all shots)."""
    total = len(chunk.get("shots", []))
    if name is None:
        return list(range(1, total + 1))
    found = []
    for i, shot in enumerate(chunk.get("shots", []), start=1):
        for el in shot["elements"]:
            if el.kind == "character" and el.meta.get("name") == name:
                found.append(i)
                break
    return found


def _fmt_shots(shots: list[int]) -> str:
    if not shots:
        return "appears in [Shot 1]"
    if len(shots) == 1:
        return f"appears in [Shot {shots[0]}]"
    return "appears throughout" if shots == list(range(1, max(shots) + 1)) else (
        "appears in " + ", ".join(f"[Shot {i}]" for i in shots)
    )


def _speaker_order(char: Character) -> int:
    """Numeric speaker order (lexicographic sort would put S10 before S2)."""
    try:
        return int((char.speaker_id or "")[1:])
    except ValueError:
        return 0


def propose(chunk: dict, bible: list[Character] = ()) -> dict:
    """Propose reference slots for one chunk's R2V prompt.

    Subject 1 is always the scene environment; following numbers go to the
    chunk's characters in bible order. Each vocal speaker gets an ``<Audio N>``
    voice-timbre reference. Sources are placeholders the user fulfills.
    """
    subjects: list[dict] = []
    context = (chunk.get("context") or "").strip()
    if context:
        subjects.append(
            {
                "label": "<Subject 1>",
                "kind": "environment",
                "name": context,
                "description": "",
                "speaker_id": None,
                "shots": _subject_shots(chunk, None),
                "shots_text": _fmt_shots(_subject_shots(chunk, None)),
                "source": "placeholder — attach an environment reference image",
            }
        )
    for char in bible:
        if char.name not in chunk.get("speakers", {}):
            continue
        subjects.append(
            {
                "label": f"<Subject {len(subjects) + 1}>",
                "kind": "character",
                "name": char.name,
                "description": char.description,
                "speaker_id": char.speaker_id,
                "shots": _subject_shots(chunk, char.name),
                "shots_text": _fmt_shots(_subject_shots(chunk, char.name)),
                "source": "placeholder — attach a character reference image",
            }
        )
    by_name = {s["name"]: s["label"] for s in subjects if s["kind"] == "character"}
    audios: list[dict] = []
    for char in sorted(
        (c for c in bible if c.speaker_id and c.name in chunk.get("speakers", {})),
        key=_speaker_order,
    ):
        audios.append(
            {
                "label": f"<Audio {len(audios) + 1}>",
                "role": TIMBRE_ROLE,
                "subject": by_name.get(char.name, ""),
                "speaker_id": char.speaker_id,
                "language": "English",
                "source": "placeholder — attach a voice sample",
            }
        )
    task_types = ["reference generation"]
    if audios:
        task_types.append("audio reference")
    return {
        "subjects": subjects,
        "pictures": [],
        "videos": [],
        "audios": audios,
        "task_types": task_types,
        "title_by_name": {s["name"]: title(s["name"]) for s in subjects if s["kind"] == "character"},
    }
