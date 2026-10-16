"""LLM client + per-mode prompt assembly over stdlib urllib.

``chat`` performs one OpenAI-compatible ``/chat/completions`` call with no
third-party SDK. ``messages`` builds the system prompt (from ``prompts``) plus
a compact, structured brief of the chunk and character bible, and ``rewrite``
sends it and returns the model's prompt text. The rule-based templates in
``fallback``/``r2v`` stay as the offline fallback (see ``h3_builder.build``).
"""
from __future__ import annotations

import json
import urllib.request

from . import prompts
from .characters import Character, title
from .config import load
from .modes import instruction_line
from .ref_manifest import propose


def chat(messages: list[dict], base_url: str | None = None, model: str | None = None,
         temperature: float | None = None, timeout: int = 120) -> str:
    """POST /chat/completions and return the assistant content (no SDK needed)."""
    cfg = load()
    base = (base_url or cfg["llm"]["base_url"]).rstrip("/")
    payload = {
        "model": model or cfg["llm"]["model"],
        "messages": messages,
        "temperature": cfg["llm"]["temperature"] if temperature is None else temperature,
    }
    req = urllib.request.Request(
        f"{base}/chat/completions",
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        body = json.loads(resp.read().decode("utf-8"))
    return body["choices"][0]["message"]["content"]


def _character_lines(bible: list[Character]) -> list[str]:
    lines = []
    for char in bible:
        sid = char.speaker_id or "no speaker ID (never vocalizes)"
        desc = f", {char.description}" if char.description else ""
        lines.append(f"- {title(char.name)} ({sid}){desc}")
    return lines or ["- (no characters detected)"]


def _beat_lines(chunk: dict) -> list[str]:
    lines: list[str] = []
    last: str | None = None
    for el in chunk.get("elements", []):
        if el.kind == "character":
            last = el.meta.get("name", "")
        elif el.kind == "parenthetical":
            who = title(last) if last else "the speaker"
            lines.append(f"- DELIVERY for {who}: {el.text.strip()}")
        elif el.kind == "dialogue":
            who = title(last) if last else "an unseen speaker"
            lines.append(f"- DIALOGUE ({who}): {el.text.strip()}")
        elif el.kind == "action":
            lines.append(f"- ACTION: {el.text.strip()}")
    return lines or ["- (no beats detected)"]


def _reference_lines(chunk: dict, bible: list[Character], manifest: dict | None) -> list[str]:
    manifest = manifest or propose(chunk, bible)
    lines: list[str] = []
    for sub in manifest["subjects"]:
        sid = f" ({sub['speaker_id']})" if sub.get("speaker_id") else ""
        desc = f", {sub['description']}" if sub.get("description") else ""
        lines.append(f"- {sub['label']}: {sub['kind']} \"{sub['name']}\"{sid}{desc}")
    for audio in manifest["audios"]:
        lines.append(
            f"- {audio['label']}: {audio['role']} for {audio['subject']} "
            f"({audio['speaker_id']})"
        )
    return lines or ["- (no reference slots proposed)"]


def _user_content(chunk: dict, bible: list[Character], mode: str, style: str,
                  manifest: dict | None = None) -> str:
    duration = float(chunk.get("duration", 8.0))
    shots = chunk.get("shots", [])
    parts = [
        f"Rewrite this chunk into an H3 prompt in {mode} mode.",
        "",
        f"Scene: {chunk.get('context') or '(no slugline)'}",
        f"Effective duration: {duration:.2f} seconds",
        f"Shots to write: {len(shots) or 1}",
        f"Visual style: {style}",
    ]
    instruction = instruction_line(mode, final_shot=max(len(shots), 1), duration=duration)
    if instruction:
        parts += [
            "",
            "Use this exact instruction line as the first line, followed by one blank line:",
            instruction,
        ]
    parts += ["", "Character bible:"]
    parts += _character_lines(bible)
    parts += ["", "Script beats in order:"]
    parts += _beat_lines(chunk)
    if mode == "R2V":
        parts += [
            "",
            "Reference slots proposed for this chunk (definitions, summary, and "
            "retention_analysis must cover these):",
        ]
        parts += _reference_lines(chunk, bible, manifest)
    return "\n".join(parts)


def messages(chunk: dict, bible: list[Character] = (), mode: str = "T2VA",
             style: str = "Live-action, cinematic", manifest: dict | None = None) -> list[dict]:
    """Assemble the system + user messages for one chunk rewrite."""
    return [
        {"role": "system", "content": prompts.system_prompt(mode)},
        {"role": "user", "content": _user_content(chunk, bible, mode, style, manifest)},
    ]


def rewrite(chunk: dict, bible: list[Character] = (), mode: str = "T2VA",
            style: str = "Live-action, cinematic", chat_fn=None) -> str:
    """Rewrite a chunk into H3 prompt text via the LLM (chat_fn injectable)."""
    msgs = messages(chunk, bible, mode=mode, style=style)
    return (chat_fn or chat)(msgs)
