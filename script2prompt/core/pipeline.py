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
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

from script2prompt.parsers import parse_file
from script2prompt.parsers.base import Element

from . import chunker, h3_builder, ref_manifest, validator
from . import scenes as scenes_mod
from .characters import Character, build_bible, title
from .modes import instruction_line

# Schema version stamped on every persisted artifact (manifest.json,
# reference_manifest.json; the future .s2p project file). Bump on any
# incompatible shape change and register the migration below.
SCHEMA_VERSION = 1

# version -> callable(data) -> data. Version 0 is "written before versioning":
# the shape was already compatible, so the migration is the identity and only
# stamps the version. Add real transforms as 1->2, 2->3, ... when shapes change.
_MIGRATIONS: dict[int, Callable[[dict], dict]] = {0: lambda artifact: artifact}


def migrate_artifact(data: dict) -> dict:
    """Bring a loaded artifact up to ``SCHEMA_VERSION`` (forward-compatible).

    Missing ``schema_version`` means a pre-versioning artifact (version 0) and
    is upgraded through the registered migrations. An artifact from a *newer*
    writer is returned unchanged rather than corrupted.
    """
    version = data.get("schema_version", 0)
    if not isinstance(version, int) or isinstance(version, bool):
        raise ValueError(f"invalid schema_version: {version!r}")
    while version < SCHEMA_VERSION:
        migration = _MIGRATIONS.get(version)
        if migration is None:
            break
        data = migration(data)
        version += 1
    data["schema_version"] = version
    return data


def load_artifact(path: str | Path) -> dict:
    """Load a JSON export artifact and migrate it to the current schema."""
    return migrate_artifact(json.loads(Path(path).read_text(encoding="utf-8")))


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
    duration = min(max(duration, chunker.MIN_SECONDS), chunker.CAP_SECONDS)
    shots_max = min(max(int(shots_max), 1), 3)
    found = scenes_mod.split(elements)
    if bible is None:
        bible = build_bible(found)
    results: list[ChunkResult] = []
    index = 0
    for scene in found:
        for chunk in chunker.chunk(scene, bible, duration=duration, shots_max=shots_max, mode=mode):
            index += 1
            prompt = h3_builder.build(chunk, bible, mode=mode, style=style, rewrite=rewrite)
            issues = validator.validate(prompt, mode=mode, duration=chunk["duration"], bible=bible)
            results.append(ChunkResult(index, scene.get("context", ""), chunk, prompt, issues))
    return Project(mode, duration, shots_max, style, found, bible, results)


def budgets(project: Project) -> dict:
    """Per-chunk and project-level budget usage (chars, duration, shots)."""
    chunks = []
    for res in project.results:
        size = len(res.prompt)
        chunks.append(
            {
                "index": res.index,
                "chars": size,
                "char_budget": validator.CHAR_BUDGET,
                "char_ratio": round(size / validator.CHAR_BUDGET, 3),
                "duration": res.chunk["duration"],
                "shots": len(res.chunk["shots"]),
                "over_budget": size > validator.CHAR_BUDGET,
            }
        )
    return {
        "char_budget": validator.CHAR_BUDGET,
        "chunks": chunks,
        "total_chars": sum(c["chars"] for c in chunks),
        "total_duration": round(sum(c["duration"] for c in chunks), 3),
        "over_budget": [c["index"] for c in chunks if c["over_budget"]],
    }


def lint(project: Project) -> list[str]:
    """Aggregate validator issues plus project-level warnings."""
    warnings: list[str] = []
    if not project.bible:
        warnings.append("no characters detected in the screenplay")
    if not project.results:
        warnings.append("no chunks generated")
    for res in project.results:
        for issue in res.issues:
            warnings.append(f"chunk {res.index}: {issue}")
    return warnings


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
        "schema_version": SCHEMA_VERSION,
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
    return {"schema_version": SCHEMA_VERSION, "mode": project.mode, "chunks": chunks}


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


_PACK_FIXED = ("prompts.md", "manifest.json", "reference_manifest.json", "characters.md")


def write_pack(project: Project, out_dir: str | Path, *, clean: bool = False) -> list[str]:
    """Write the export pack to ``out_dir``; return the filenames written.

    With ``clean=True``, stale artifacts from a previous pack in the same
    directory (the fixed export names and ``chunk_*.txt``) are removed before
    writing, so re-running a smaller project does not leave orphaned files.
    """
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    pack = export_pack(project)
    if clean:
        stale = set(_PACK_FIXED) | {p.name for p in out.glob("chunk_*.txt")}
        for name in sorted(stale):
            (out / name).unlink(missing_ok=True)
    written: list[str] = []
    for name, content in pack.items():
        (out / name).write_text(content, encoding="utf-8")
        written.append(name)
    return written
