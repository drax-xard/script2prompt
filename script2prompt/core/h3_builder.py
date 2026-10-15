"""H3 prompt assembly (Milestone 1: T2VA via rule-based fallback).

Milestone 4 will make the LLM rewrite primary with this as fallback;
other modes arrive in Milestones 2-3.
"""
from __future__ import annotations

from . import fallback
from .characters import Character


def build(chunk: dict, bible: list[Character] = (), mode: str = "T2VA",
          style: str = "Live-action, cinematic") -> str:
    """Assemble the H3 prompt text for a chunk."""
    return fallback.build(chunk, bible=bible, mode=mode, style=style)
