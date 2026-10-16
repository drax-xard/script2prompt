"""End-to-end pipeline + export pack (Milestone 6).

UI-agnostic glue shared by the Streamlit wizard (``app/web.py``) and the CLI
(``python -m script2prompt``): parse -> scenes -> bible -> chunks -> prompts ->
validation, plus the export artifacts (``prompts.md``, ``manifest.json``,
``reference_manifest.json`` for non-T2VA modes, ``characters.md``, per-chunk
``.txt``).
"""
from __future__ import annotations

import json
import tempfile
from dataclasses import dataclass
from pathlib import Path

from script2prompt.parsers import parse_file
from script2prompt.parsers.base import Element

from . import chunker, h3_builder, ref_manifest, validator
from . import scenes as scenes_mod
from .characters import Character, build_bible, title
from .modes import instruction_line


@dataclass
class ChunkResult:
    index: int
    scene: str
    chunk: dict
    prompt: str
    issues: list[str]


@dataclass
class Project:
    mode: str
    duration: float
    shots_max: int
    style: str
    scenes: list[dict]
    bible: list[Character]
    results: list[ChunkResult]


def parse_bytes(data: bytes, filename: str) -> list[Element]:
    """Parse an uploaded file's bytes by writing a temp file with its suffix."""
    suffix = Path(filename).suffix or ".txt"
    with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as fh:
        fh.write(data)
        tmp = fh.name
    try:
        return parse_file(tmp)
    finally:
        Path(tmp).unlink(missing_ok=True)


def run(elements: list[Element], *, mode: str = "T2VA", duration: float = 8.0,
        shots_max: int = 3, style: str = "Live-action, cinematic",
        bible: list[Character] | None = None, rewrite=None) -> Project:
    """Parse-to-prompts for one project (mode locked for all chunks)."""
    found = scenes_mod.split(elements)
    if bible is None:
        bible = build_bible(found)
    results: list[ChunkResult] = []
    index = 0
    for scene in found:
        for chunk in chunker.chunk(scene, bible, duration=duration, shots_max=shots_max, mode=mode):
            index += 1
            prompt = h3_builder.build(chunk, bible, mode=mode, style=style, rewrite=rewrite)
            issues = validator.validate(prompt, mode=mode, duration=chunk["duration"])
            results.append(ChunkResult(index, scene.get("context", ""), chunk, prompt, issues))
    return Project(mode, duration, shots_max, style, found, bible, results)


def characters_markdown(bible: list[Character]) -> str:
    lines = ["# Characters", ""]
    if not bible:
        lines.append("_No characters detected._")
    for char in bible:
        sid = f" ({char.speaker_id})" if char.speaker_id else ""
        desc = f" — {char.description}" if char.description else ""
        lines.append(f"- **{title(char.name)}**{sid}{desc}")
    return "\n".join(lines) + "\n"


def prompts_markdown(project: Project) -> str:
    blocks = [f"# H3 Prompts ({project.mode})", ""]
    for res in project.results:
        blocks += [f"## Chunk {res.index} — {project.mode} ({res.chunk['duration']:.2f}s)", ""]
        if res.scene:
            blocks += [f"_Scene: {res.scene}_", ""]
        if res.issues:
            blocks += [f"WARNING: {'; '.join(res.issues)}", ""]
        blocks += ["```", res.prompt, "```", ""]
    return "\n".join(blocks).rstrip() + "\n"


def manifest(project: Project) -> dict:
    return {
        "mode": project.mode,
        "duration_target": project.duration,
        "shots_max": project.shots_max,
        "style": project.style,
        "characters": [
            {
                "name": char.name,
                "title": title(char.name),
                "speaker_id": char.speaker_id,
                "description": char.description,
            }
            for char in project.bible
        ],
        "chunks": [
            {
                "index": res.index,
                "scene": res.scene,
                "duration": res.chunk["duration"],
                "shots": [{"start": shot["start"]} for shot in res.chunk["shots"]],
                "speakers": {name: c.speaker_id for name, c in res.chunk["speakers"].items()},
                "issues": res.issues,
            }
            for res in project.results
        ],
    }


def reference_manifest(project: Project) -> dict:
    """Mode-aware reference checklist (non-T2VA modes)."""
    chunks = []
    for res in project.results:
        final_shot = max(len(res.chunk["shots"]), 1)
        entry: dict = {
            "index": res.index,
            "instruction_line": instruction_line(
                project.mode, final_shot=final_shot, duration=res.chunk["duration"]
            ),
        }
        if project.mode == "R2V":
            entry.update(ref_manifest.propose(res.chunk, project.bible))
        else:
            entry["pictures"] = ref_manifest.picture_slots(project.mode, final_shot)
        chunks.append(entry)
    return {"mode": project.mode, "chunks": chunks}


def export_pack(project: Project) -> dict[str, str]:
    """Return the export artifacts as ``filename -> content``."""
    pack = {
        "prompts.md": prompts_markdown(project),
        "manifest.json": json.dumps(manifest(project), indent=2, ensure_ascii=False) + "\n",
        "characters.md": characters_markdown(project.bible),
    }
    if project.mode != "T2VA":
        pack["reference_manifest.json"] = (
            json.dumps(reference_manifest(project), indent=2, ensure_ascii=False) + "\n"
        )
    for res in project.results:
        pack[f"chunk_{res.index:02d}.txt"] = res.prompt + "\n"
    return pack


def write_pack(project: Project, out_dir: str | Path) -> list[str]:
    """Write the export pack to ``out_dir``; return the filenames written."""
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    written: list[str] = []
    for name, content in export_pack(project).items():
        (out / name).write_text(content, encoding="utf-8")
        written.append(name)
    return written
