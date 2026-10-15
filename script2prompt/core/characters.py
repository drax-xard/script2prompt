"""Character bible: stable descriptions + speaker IDs (S1, S2, ...)."""
from __future__ import annotations

from dataclasses import dataclass


@dataclass
class Character:
    name: str
    speaker_id: str | None  # S1.. for vocal characters, None otherwise
    description: str
