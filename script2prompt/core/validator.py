"""T2VA prompt validator/linter (Milestone 1).

Checks field presence/order, sequential shots (<=3), timestamp rules
([Shot 1] bare; later shots strictly increasing and inside duration),
balanced <d> tags with language labels, soundscape/music sentence budgets,
and the 7000-character budget.
"""
from __future__ import annotations

import re

FIELDS = (
    "integrated_multimodal_description:",
    "overall_soundscape:",
    "non_diegetic_music:",
)
CHAR_BUDGET = 7000
SHOT_STAMP = re.compile(r"\[Shot (\d+)\] At (\d{2}):(\d{2})\.(\d{3})")
SHOT_ANY = re.compile(r"\[Shot (\d+)\]")


def _sentences(text: str) -> list[str]:
    return [s.strip() for s in re.split(r"[.!?]+", text.strip()) if s.strip()]


def validate(prompt: str, mode: str = "T2VA", duration: float = 8.0) -> list[str]:
    """Return a list of issues (empty = valid)."""
    issues: list[str] = []
    if mode != "T2VA":
        return [f"{mode} validation arrives in Milestones 2-3"]

    found = [prompt.find(field) for field in FIELDS]
    if any(pos < 0 for pos in found):
        issues.append("missing required field(s)")
        return issues
    if not found[0] < found[1] < found[2]:
        issues.append("fields out of order")

    numbers = [int(n) for n in SHOT_ANY.findall(prompt)]
    if not numbers or numbers[0] != 1:
        issues.append("[Shot 1] must open the description")
    if numbers != list(range(1, len(numbers) + 1)):
        issues.append("shot numbers must be sequential from 1")
    if len(numbers) > 3:
        issues.append("more than 3 shots in one prompt")
    if re.search(r"\[Shot 1\] At ", prompt):
        issues.append("[Shot 1] must not have a timestamp")

    stamps = SHOT_STAMP.findall(prompt)
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
    for body in re.findall(r"<d>(.*?)</d>", prompt, re.S):
        if not re.match(r"\[[^\]]+\]", body.strip()):
            issues.append("dialogue tag missing language label")

    soundscape = prompt[found[1] + len(FIELDS[1]) : found[2]].strip()
    if soundscape != "N/A":
        count = len(_sentences(soundscape))
        if not 1 <= count <= 4:
            issues.append("overall_soundscape must be 1-4 sentences")
        if "<d>" in soundscape:
            issues.append("overall_soundscape must not contain dialogue")
    music = prompt[found[2] + len(FIELDS[2]) :].strip()
    if music != "N/A" and not 1 <= len(_sentences(music)) <= 3:
        issues.append("non_diegetic_music must be 1-3 sentences or N/A")

    if len(prompt) > CHAR_BUDGET:
        issues.append(f"prompt exceeds {CHAR_BUDGET} characters")
    return issues
