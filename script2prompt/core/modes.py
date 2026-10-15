"""H3 modes: instruction lines + section schemas per mode."""
from __future__ import annotations

MODES = ("T2VA", "I2VA", "FL2VA", "L2VA", "R2V")


def instruction_line(mode: str, final_shot: int = 1, duration: float = 8.0) -> str:
    """Render the mode's instruction line ('' for T2VA). TODO: Milestone 2."""
    raise NotImplementedError
