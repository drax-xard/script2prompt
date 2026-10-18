"""LLM client + per-mode prompt assembly over stdlib urllib.

``chat`` performs one OpenAI-compatible ``/chat/completions`` call with no
third-party SDK. ``messages`` builds the system prompt (from ``prompts``) plus
a compact, structured brief of the chunk and character bible, and ``rewrite``
sends it and returns the model's prompt text. The rule-based templates in
``fallback``/``r2v`` stay as the offline fallback (see ``h3_builder.build``).
"""
from __future__ import annotations

import json
import re
import time
import urllib.error
import urllib.request

from . import prompts, validator
from .characters import Character, title
from .config import load
from .modes import instruction_line
from .ref_manifest import propose
from .render import scene_phrase


class LLMError(RuntimeError):
    """The LLM endpoint is unreachable or returned an unusable response."""


def _error_detail(exc: urllib.error.HTTPError) -> str:
    """Short body excerpt from an HTTP error, for the raised message."""
    try:
        body = exc.read(200).decode("utf-8", "replace").strip()
    except Exception:  # reading the error body must never mask the original error
        return ""
    finally:
        exc.close()
    return f": {body}" if body else ""


def chat(messages: list[dict], base_url: str | None = None, model: str | None = None,
         temperature: float | None = None, max_tokens: int | None = None,
         timeout: int | None = None, retries: int | None = None) -> str:
    """POST /chat/completions and return the assistant content (no SDK needed).

    Transient failures (network errors, timeouts, 5xx) are retried with
    exponential backoff; a definitive failure raises :class:`LLMError`.
    """
    cfg = load()["llm"]
    base = (base_url or cfg["base_url"]).rstrip("/")
    payload = {
        "model": model or cfg["model"],
        "messages": messages,
        "temperature": cfg["temperature"] if temperature is None else temperature,
        "max_tokens": cfg["max_tokens"] if max_tokens is None else max_tokens,
    }
    if cfg.get("disable_thinking", True):
        # Reasoning models (Qwen3 etc.) otherwise emit a chain-of-thought preamble
        # that breaks the strict output format. Servers that ignore the field are
        # unaffected; strict servers can turn this off in config.
        payload["chat_template_kwargs"] = {"enable_thinking": False}
    timeout = cfg["timeout"] if timeout is None else timeout
    retries = max(int(cfg["retries"] if retries is None else retries), 0)
    req = urllib.request.Request(
        f"{base}/chat/completions",
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    delay = 0.5
    for attempt in range(retries + 1):
        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                body = json.loads(resp.read().decode("utf-8"))
            return body["choices"][0]["message"]["content"]
        except urllib.error.HTTPError as exc:
            detail = _error_detail(exc)  # reads (and closes) the error response
            if exc.code >= 500 and attempt < retries:
                pass  # transient server error: fall through to backoff
            else:
                raise LLMError(f"LLM endpoint returned HTTP {exc.code}{detail}") from exc
        except (urllib.error.URLError, TimeoutError) as exc:
            if attempt >= retries:
                raise LLMError(f"LLM endpoint unreachable: {exc}") from exc
        except (json.JSONDecodeError, KeyError, IndexError, TypeError) as exc:
            raise LLMError(f"malformed LLM response: {exc}") from exc
        time.sleep(delay)
        delay *= 2
    raise LLMError("LLM endpoint failed after retries")  # pragma: no cover


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
                  manifest: dict | None = None, context: str = "") -> str:
    duration = float(chunk.get("duration", 8.0))
    shots = chunk.get("shots", [])
    phrase = scene_phrase(chunk.get("context", ""))
    parts = [
        f"Rewrite this chunk into an H3 prompt in {mode} mode.",
        "",
        f"Scene slugline: {chunk.get('context') or '(no slugline)'}",
    ]
    if phrase:
        parts.append(f"Setting (describe it as): {phrase}")
    parts += [
        f"Effective duration: {duration:.2f} seconds",
        f"Shots to write: {len(shots) or 1}",
        f"Visual style: {style}",
    ]
    if context:
        parts += ["", "Story context (tone, voice, and continuity):", context]
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


_FIELD_LABELS = (
    "integrated_multimodal_description:",
    "overall_soundscape:",
    "non_diegetic_music:",
    "subject_definitions:",
    "summary:",
    "retention_analysis:",
    "detailed_description:",
)


def _fmt_time(seconds: float) -> str:
    """Format a cut time as the guide's ``MM:SS.mmm``."""
    total_ms = round(seconds * 1000)
    minutes, rem = divmod(total_ms, 60000)
    secs, millis = divmod(rem, 1000)
    return f"{minutes:02d}:{secs:02d}.{millis:03d}"


def _normalize_timestamps(prompt: str) -> str:
    """Rewrite any ``[Shot N] At <time>`` cut time into ``MM:SS.mmm``.

    Small models emit ``At 3.87s`` or ``At 0:03.5``; the validator (and guide)
    require zero-padded ``MM:SS.mmm``. ``[Shot 1]`` must carry no timestamp, so
    one is stripped if present.
    """
    time = r"(\d+(?::\d+){0,2}(?:\.\d+)?)\s*(?:s|sec|secs|seconds?)?\b"

    def _repl(match: re.Match) -> str:
        head, raw = match.group(1), match.group(2)
        parts = raw.split(":")
        if len(parts) == 3:
            secs = int(parts[0]) * 3600 + int(parts[1]) * 60 + float(parts[2])
        elif len(parts) == 2:
            secs = int(parts[0]) * 60 + float(parts[1])
        else:
            secs = float(parts[0])
        return f"{head}At {_fmt_time(secs)}"

    prompt = re.sub(rf"(\[Shot \d+\] )At {time}", _repl, prompt)
    return re.sub(r"\[Shot 1\] At \d{2}:\d{2}\.\d{3}[,]?\s*", "[Shot 1] ", prompt)


def _section_end(prompt: str, label: str) -> int | None:
    """End offset of a field label that sits alone on its own line."""
    match = re.search(rf"(?m)^{re.escape(label)}[ \t]*$", prompt)
    return match.end() if match else None


def _reattach_dialogue(prompt: str) -> str:
    """Move stray dialogue lines back inside the description field.

    Small models often append spoken lines after ``non_diegetic_music`` (or in a
    separate block) instead of inside the shot narration. Any such line is
    relocated to just before ``overall_soundscape``, which is where the guide
    requires dialogue within the description.
    """
    music_end = _section_end(prompt, "non_diegetic_music:")
    if music_end is None:
        return prompt
    if not re.search(r"(?m)^(?:integrated_multimodal_description|detailed_description):", prompt):
        return prompt
    body = prompt[music_end:]
    moved, kept = [], []
    for line in body.splitlines():
        if line.strip() and ("<d>" in line or re.search(r"\)\s*says?\b", line)):
            moved.append(line.strip())
        else:
            kept.append(line)
    if not moved:
        return prompt
    head = prompt[:music_end]
    sound_start = re.search(r"(?m)^overall_soundscape:[ \t]*$", head)
    insert = sound_start.start() if sound_start else len(head)
    head = head[:insert].rstrip() + "\n" + "\n".join(moved) + "\n\n" + head[insert:]
    return head + "\n".join(kept)


def _cap_sentences(segment: str, cap: int) -> str:
    """Trim a field body to at most ``cap`` sentences, keeping surrounding whitespace."""
    match = re.match(r"(\s*)(.*?)(\s*)$", segment, re.S)
    lead, core, trail = match.groups()
    parts = [p.strip() for p in re.split(r"(?<=[.!?])\s+", core.strip()) if p.strip()]
    if len(parts) <= cap:
        return segment
    return lead + " ".join(parts[:cap]) + trail


def _cap_audio_field(prompt: str, label: str, cap: int) -> str:
    """Apply the guide's sentence budget to a labelled audio field."""
    start = _section_end(prompt, label)
    if start is None:
        return prompt
    nxt = re.search(r"(?m)^[a-z_]+:[ \t]*$", prompt[start:])
    end = start + nxt.start() if nxt else len(prompt)
    return prompt[:start] + _cap_sentences(prompt[start:end], cap) + prompt[end:]


def sanitize(prompt: str) -> str:
    """Fix the deviations small models make most often.

    Moves a field label onto its own line when the model inlined the body, and
    repairs the dialogue language tag: an ``[Lang]`` written after ``</d>`` is
    dropped, and any ``<d>`` block missing a tag gets ``[English]`` (v1 assumes
    English dialogue). Structure-preserving: only these patterns change.
    """
    for label in _FIELD_LABELS:
        prompt = re.sub(
            rf"(?m)^{re.escape(label)}[ \t]+",
            label + "\n",
            prompt,
        )
    # "<d>words</d> (English)" -> "<d>words</d>"
    prompt = re.sub(r"</d>\s*[\(\[]\s*[A-Za-z][A-Za-z /-]*\s*[\)\]]", "</d>", prompt)

    def _tag(match: re.Match) -> str:
        body = match.group(1)
        if re.match(r"\s*\[[^\]]+\]", body):
            return match.group(0)
        return f"<d>[English]{body}</d>"

    prompt = re.sub(r"<d>(.*?)</d>", _tag, prompt, flags=re.S)
    prompt = _normalize_timestamps(prompt)
    prompt = _reattach_dialogue(prompt)
    prompt = _cap_audio_field(prompt, "overall_soundscape:", 4)
    return _cap_audio_field(prompt, "non_diegetic_music:", 3)


def messages(chunk: dict, bible: list[Character] = (), mode: str = "T2VA",
             style: str = "Live-action, cinematic", manifest: dict | None = None,
             context: str = "") -> list[dict]:
    """Assemble the system + user messages for one chunk rewrite."""
    return [
        {"role": "system", "content": prompts.system_prompt(mode)},
        {"role": "user", "content": _user_content(chunk, bible, mode, style, manifest, context)},
    ]


def rewrite(chunk: dict, bible: list[Character] = (), mode: str = "T2VA",
            style: str = "Live-action, cinematic", chat_fn=None, context: str = "",
            fix_attempts: int | None = None) -> str:
    """Rewrite a chunk into H3 prompt text, repairing validator issues.

    The first model response is validated; while it still has issues, up to
    ``fix_attempts`` repair turns feed the exact problems back and the model is
    asked for a corrected prompt. The version with the fewest issues is
    returned, so a failed repair never discards usable model output.
    """
    send = chat_fn or chat
    msgs = messages(chunk, bible, mode=mode, style=style, context=context)
    text = sanitize((send(msgs) or "").strip())
    if not text:
        return ""
    if fix_attempts is None:
        fix_attempts = load()["llm"].get("fix_attempts", 1)
    duration = float(chunk.get("duration", 8.0))
    best = text
    best_issues = validator.validate(best, mode=mode, duration=duration, bible=list(bible))
    for _ in range(max(int(fix_attempts), 0)):
        if not best_issues:
            break
        repair = msgs + [
            {"role": "assistant", "content": best},
            {
                "role": "user",
                "content": (
                    "That prompt failed validation: " + "; ".join(best_issues) + ". "
                    "Reply with ONLY the corrected prompt, keeping each field label "
                    "alone on its own line and dialogue as Name (S1) says "
                    "<d>[English]words</d>."
                ),
            },
        ]
        try:
            candidate = sanitize((send(repair) or "").strip())
        except LLMError:
            break
        if not candidate:
            break
        issues = validator.validate(candidate, mode=mode, duration=duration, bible=list(bible))
        if len(issues) < len(best_issues):
            best, best_issues = candidate, issues
    return best


_CONTEXT_SYSTEM = """You are a script supervisor preparing a short video-generator
brief. Read the screenplay digest and reply with plain text only (no headings, no
lists, at most 120 words) covering: the overall tone and genre; the visual
style and color palette that fits; and a one-line voice note for each speaking
character (age, vocal quality, delivery). No preamble, no commentary."""


def _digest(elements: list, bible: list[Character]) -> str:
    sluglines: list[str] = []
    beats: list[str] = []
    for el in elements:
        if el.kind == "heading" and el.text not in sluglines:
            sluglines.append(el.text)
        elif el.kind == "action" and len(beats) < 12:
            beats.append(el.text)
    lines: list[str] = []
    if sluglines:
        lines.append("Sluglines: " + "; ".join(sluglines[:8]))
    if beats:
        lines.append("Actions:")
        lines += [f"- {beat}" for beat in beats]
    if bible:
        lines.append("Characters:")
        lines += [
            f"- {title(c.name)} ({c.speaker_id or 'silent'}): {c.description or 'no description'}"
            for c in bible
        ]
    return "\n".join(lines) or "(empty screenplay)"


def project_context(elements: list, bible: list[Character], *, chat_fn=None, style: str = "") -> str:
    """One optional per-project call: tone, palette, and per-character voice notes."""
    user = "Screenplay digest:\n" + _digest(elements, bible)
    if style:
        user += f"\nConfigured visual style: {style}"
    try:
        reply = (chat_fn or chat)(
            [
                {"role": "system", "content": _CONTEXT_SYSTEM},
                {"role": "user", "content": user},
            ]
        )
    except LLMError:
        return ""
    return (reply or "").strip()


class Rewriter:
    """Per-project rewrite callable carrying a one-time story brief.

    Construct once per project so the optional context call runs a single time;
    an instance is callable with the ``(chunk, bible, mode=, style=)`` signature
    that ``h3_builder.build`` expects. The context is computed lazily and cached.
    """

    def __init__(self, elements: list, bible: list[Character], *, context: bool = True,
                 chat_fn=None, style: str = "", fix_attempts: int | None = None) -> None:
        self.elements = list(elements)
        self.bible = list(bible)
        self.style = style
        self._chat_fn = chat_fn
        self._context_enabled = context
        self._fix_attempts = fix_attempts
        self._context: str | None = None

    @property
    def context(self) -> str:
        if self._context is None:
            self._context = (
                project_context(self.elements, self.bible, chat_fn=self._chat_fn, style=self.style)
                if self._context_enabled
                else ""
            )
        return self._context

    def __call__(self, chunk: dict, bible: list[Character] | None = None, mode: str = "T2VA",
                 style: str = "Live-action, cinematic") -> str:
        return rewrite(
            chunk,
            bible if bible is not None else self.bible,
            mode=mode,
            style=style or self.style,
            chat_fn=self._chat_fn,
            context=self.context,
            fix_attempts=self._fix_attempts,
        )
