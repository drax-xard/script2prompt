"""H3 prompt assembly: LLM rewrite primary, rule-based templates as fallback.

Call ``build`` with a ``rewrite`` callable (e.g. ``llm.rewrite``) to use the
LLM. The model's text is returned when non-empty; any raised error, empty
result, or omitted callable falls back to the deterministic ``fallback``/``r2v``
builders (Milestones 1-3), so generation never hard-fails offline.
"""
from __future__ import annotations

from typing import Callable

from . import fallback, r2v
from .characters import Character

Rewrite = Callable[..., str]


def _template(chunk: dict, bible: list[Character], mode: str, style: str) -> str:
    if mode == "R2V":
        return r2v.build(chunk, bible=bible, style=style)
    return fallback.build(chunk, bible=bible, mode=mode, style=style)


def build(chunk: dict, bible: list[Character] = (), mode: str = "T2VA",
          style: str = "Live-action, cinematic", rewrite: Rewrite | None = None) -> str:
    """Assemble the H3 prompt for a chunk (LLM when available, else template)."""
    if rewrite is not None:
        try:
            text = rewrite(chunk, bible, mode=mode, style=style)
        except Exception:  # offline / bad endpoint / malformed response: use template
            text = ""
        if text and text.strip():
            return text.strip()
    return _template(chunk, bible, mode, style)
