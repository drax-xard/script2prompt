"""Prompt validator/linter (Milestones 1-2: T2VA + keyframe modes).

Checks the instruction line for I2VA/FL2VA/L2VA, then the shared rules:
field presence/order, sequential shots (<=3), timestamp rules ([Shot 1]
bare; later shots strictly increasing and inside duration), balanced <d>
tags with language labels, soundscape/music sentence budgets, and the
7000-character budget. R2V arrives in Milestone 3.
"""
from __future__ import annotations

import re

from .modes import BASE_FIELDS, instruction_line

CHAR_BUDGET = 7000
SHOT_STAMP = re.compile(r"\[Shot (\d+)\] At (\d{2}):(\d{2})\.(\d{3})")
SHOT_ANY = re.compile(r"\[Shot (\d+)\]")
FIELDS = BASE_FIELDS


def _sentences(text: str) -> list[str]:
    return [s.strip() for s in re.split(r"[.!?]+", text.strip()) if s.strip()]


def validate(prompt: str, mode: str = "T2VA", duration: float = 8.0) -> list[str]:
    """Return a list of issues (empty = valid)."""
    issues: list[str] = []
    if mode == "R2V":
        return ["R2V validation arrives in Milestone 3"]
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

    if prompt.count("<d>") != prompt.count("</d>"):
        issues.append("unbalanced <d> tags")
    for item in re.findall(r"<d>(.*?)</d>", prompt, re.S):
        if not re.match(r"\[[^\]]+\]", item.strip()):
            issues.append("dialogue tag missing language label")

    soundscape = body[found[1] + len(FIELDS[1]) : found[2]].strip()
    if soundscape != "N/A":
        count = len(_sentences(soundscape))
        if not 1 <= count <= 4:
            issues.append("overall_soundscape must be 1-4 sentences")
        if "<d>" in soundscape:
            issues.append("overall_soundscape must not contain dialogue")
    music = body[found[2] + len(FIELDS[2]) :].strip()
    if music != "N/A" and not 1 <= len(_sentences(music)) <= 3:
        issues.append("non_diegetic_music must be 1-3 sentences or N/A")

    if len(prompt) > CHAR_BUDGET:
        issues.append(f"prompt exceeds {CHAR_BUDGET} characters")
    return issues
