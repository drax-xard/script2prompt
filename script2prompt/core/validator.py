"""Prompt validator/linter (Milestones 1-3: base modes + R2V).

Checks the instruction line for I2VA/FL2VA/L2VA, the six R2V sections with
valid retention markers and consistent reference labels, then the shared
rules: field presence/order, sequential shots (<=3), timestamp rules
([Shot 1] bare; later shots strictly increasing and inside duration),
balanced <d> tags with language labels, soundscape/music sentence budgets,
and the 7000-character budget.
"""
from __future__ import annotations

import re

from .modes import BASE_FIELDS, R2V_SECTIONS, instruction_line

CHAR_BUDGET = 7000
SHOT_STAMP = re.compile(r"\[Shot (\d+)\] At (\d{2}):(\d{2})\.(\d{3})")
SHOT_ANY = re.compile(r"\[Shot (\d+)\]")
LABEL_USE = re.compile(r"<(Subject|Picture|Video|Audio) (\d+)>")
SPEAKER_ID = re.compile(r"\(S\d+(?:,S\d+)*\)")
VISUAL_MARKERS = frozenset({"fully_preserved", "partially_preserved", "attribute_transfer", "weak_reference"})
AUDIO_MARKERS = frozenset({"fully_copy", "partially_copy", "reference", "weak_reference"})
FIELDS = BASE_FIELDS


def _sentences(text: str) -> list[str]:
    return [s.strip() for s in re.split(r"[.!?]+", text.strip()) if s.strip()]


def validate(prompt: str, mode: str = "T2VA", duration: float = 8.0,
             bible: list | None = None) -> list[str]:
    """Return a list of issues (empty = valid)."""
    issues: list[str] = []
    if mode == "R2V":
        return _validate_r2v(prompt, duration, bible)
    if mode not in ("T2VA", "I2VA", "FL2VA", "L2VA"):
        return [f"unknown mode: {mode}"]

    body = prompt
    if mode != "T2VA":
        lines = prompt.splitlines()
        # Shot labels inside the instruction line must not pollute the count.
        looks_like_instruction = bool(lines) and (
            lines[0].startswith("For the target video")
            or lines[0].startswith("How the reference pictures")
        )
        if looks_like_instruction:
            rest = lines[1:]
            body = "\n".join(rest[1:]) if rest[:1] == [""] else "\n".join(rest)
            if rest[:1] != [""]:
                issues.append("blank line required after the instruction line")
        else:
            issues.append(f"missing {mode} instruction line")
        shot_count = len(SHOT_ANY.findall(body))
        if looks_like_instruction:
            expected = instruction_line(mode, final_shot=max(shot_count, 1), duration=duration)
            if lines[0] != expected:
                issues.append(f"incorrect {mode} instruction line")
        if mode == "FL2VA" and shot_count > 1:
            issues.append("FL2VA favors a single shot per prompt")

    found = [body.find(field) for field in FIELDS]
    if any(pos < 0 for pos in found):
        issues.append("missing required field(s)")
        return issues
    if not found[0] < found[1] < found[2]:
        issues.append("fields out of order")

    issues.extend(_check_shots(body, duration))
    issues.extend(_check_dialogue(prompt))
    issues.extend(_check_speakers(prompt, bible))
    issues.extend(_check_soundscape(body[found[1] + len(FIELDS[1]) : found[2]].strip()))
    issues.extend(_check_music(body[found[2] + len(FIELDS[2]) :].strip()))

    if len(prompt) > CHAR_BUDGET:
        issues.append(f"prompt exceeds {CHAR_BUDGET} characters")
    return issues


def _check_shots(body: str, duration: float) -> list[str]:
    issues: list[str] = []
    numbers = [int(n) for n in SHOT_ANY.findall(body)]
    if not numbers or numbers[0] != 1:
        issues.append("[Shot 1] must open the description")
    if numbers != list(range(1, len(numbers) + 1)):
        issues.append("shot numbers must be sequential from 1")
    if len(numbers) > 3:
        issues.append("more than 3 shots in one prompt")
    if re.search(r"\[Shot 1\] At ", body):
        issues.append("[Shot 1] must not have a timestamp")

    stamps = SHOT_STAMP.findall(body)
    if len(stamps) != max(len(numbers) - 1, 0):
        issues.append("each shot after the first needs one At MM:SS.mmm timestamp")
    times = [int(mm) * 60 + int(ss) + int(ms) / 1000 for _, mm, ss, ms in stamps]
    for earlier, later in zip(times, times[1:]):
        if not later > earlier:
            issues.append("cut times must strictly increase")
            break
    for cut in times:
        if not 0 < cut < duration + 1e-9:
            issues.append(f"cut time {cut:.3f}s outside duration {duration:.2f}s")
    return issues


def _check_dialogue(text: str) -> list[str]:
    issues: list[str] = []
    if text.count("<d>") != text.count("</d>"):
        issues.append("unbalanced <d> tags")
    for item in re.findall(r"<d>(.*?)</d>", text, re.S):
        if not re.match(r"\[[^\]]+\]", item.strip()):
            issues.append("dialogue tag missing language label")
    return issues


def _check_speakers(text: str, bible: list | None = None) -> list[str]:
    issues: list[str] = []
    if "unseen speaker" in text.lower():
        issues.append("dialogue attributed to an unseen speaker (missing character cue)")
    if bible is not None:
        valid = {c.speaker_id for c in bible if c.speaker_id}
        for sid in re.findall(r"\(S(\d+)(?:,S\d+)*\)", text):
            if f"S{sid}" not in valid:
                issues.append(f"speaker ID S{sid} not in the character bible")
    return issues


def _check_soundscape(text: str) -> list[str]:
    issues: list[str] = []
    if text != "N/A":
        count = len(_sentences(text))
        if not 1 <= count <= 4:
            issues.append("overall_soundscape must be 1-4 sentences")
        if "<d>" in text:
            issues.append("overall_soundscape must not contain dialogue")
    return issues


def _check_music(text: str) -> list[str]:
    if text != "N/A" and not 1 <= len(_sentences(text)) <= 3:
        return ["non_diegetic_music must be 1-3 sentences or N/A"]
    return []


def _section(prompt: str, label: str, following: tuple[str, ...]) -> str:
    start = prompt.find(label)
    if start < 0:
        return ""
    start += len(label)
    end = min(
        ([prompt.find(other, start) for other in following if prompt.find(other, start) >= 0] or [len(prompt)])
    )
    return prompt[start:end].strip()


def _validate_r2v(prompt: str, duration: float, bible: list | None = None) -> list[str]:
    issues: list[str] = []
    found = [prompt.find(section) for section in R2V_SECTIONS]
    if any(pos < 0 for pos in found):
        return ["missing required R2V section(s)"]
    if not all(a < b for a, b in zip(found, found[1:])):
        issues.append("R2V sections out of order")

    definitions = _section(prompt, "subject_definitions:", R2V_SECTIONS[1:])
    defined = set()
    for line in definitions.splitlines():
        opened = re.match(r"<(Subject|Picture|Video|Audio) (\d+)>", line.strip())
        if opened:
            defined.add(f"<{opened.group(1)} {opened.group(2)}>")
    if not defined:
        issues.append("subject_definitions defines no reference labels")

    summary = _section(prompt, "summary:", R2V_SECTIONS[2:])
    if not re.search(r"\[.+\]", summary):
        issues.append("summary needs a [task-type] prefix")

    retention = _section(prompt, "retention_analysis:", R2V_SECTIONS[3:])
    for line in [ln.strip() for ln in retention.splitlines() if ln.strip()]:
        marker = re.search(r":\s*([a-z_]+)\s*-", line)
        if line.startswith("<Audio"):
            if not marker or marker.group(1) not in AUDIO_MARKERS:
                issues.append(f"invalid audio retention marker: {line[:60]}")
        elif line.startswith("<"):
            if not marker or marker.group(1) not in VISUAL_MARKERS:
                issues.append(f"invalid visual retention marker: {line[:60]}")
    if SPEAKER_ID.search(retention):
        issues.append("retention_analysis must not contain speaker IDs")

    for kind, num in LABEL_USE.findall(prompt):
        if f"<{kind} {num}>" not in defined:
            issues.append(f"undefined reference label: <{kind} {num}>")

    detailed = _section(prompt, "detailed_description:", R2V_SECTIONS[4:])
    issues.extend(_check_shots(detailed, duration))
    issues.extend(_check_dialogue(prompt))
    issues.extend(_check_speakers(prompt, bible))
    issues.extend(_check_soundscape(_section(prompt, "overall_soundscape:", R2V_SECTIONS[5:])))
    issues.extend(_check_music(_section(prompt, "non_diegetic_music:", ())))
    if len(prompt) > CHAR_BUDGET:
        issues.append(f"prompt exceeds {CHAR_BUDGET} characters")
    return issues
