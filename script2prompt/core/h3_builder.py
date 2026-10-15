"""H3 prompt assembly (Milestones 1-3: rule-based builders per mode).

Milestone 4 will make the LLM rewrite primary with these as fallback.
"""
from __future__ import annotations

from . import fallback, r2v
from .characters import Character


def build(chunk: dict, bible: list[Character] = (), mode: str = "T2VA",
          style: str = "Live-action, cinematic") -> str:
    """Assemble the H3 prompt text for a chunk."""
    if mode == "R2V":
        return r2v.build(chunk, bible=bible, style=style)
    return fallback.build(chunk, bible=bible, mode=mode, style=style)
