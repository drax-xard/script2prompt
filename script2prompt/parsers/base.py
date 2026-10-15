"""Shared screenplay element model."""
from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class Element:
    kind: str  # heading | action | character | dialogue | parenthetical | transition
    text: str
    meta: dict = field(default_factory=dict)
