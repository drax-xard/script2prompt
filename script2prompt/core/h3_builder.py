"""H3 prompt assembly (Milestones 1-2: rule-based fallback for base modes).

Milestone 4 will make the LLM rewrite primary with this as fallback;
R2V arrives in Milestone 3.
"""
from __future__ import annotations

from . import fallback
from .characters import Character


def build(chunk: dict, bible: list[Character] = (), mode: str = "T2VA",
          style: str = "Live-action, cinematic") -> str:
    """Assemble the H3 prompt text for a chunk."""
    return fallback.build(chunk, bible=bible, mode=mode, style=style)
