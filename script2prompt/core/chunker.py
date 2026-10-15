"""Chunker: pack scene beats into <=10s, <=3-shot chunks."""
from __future__ import annotations


def chunk(scene: dict, duration: float = 8.0, shots_max: int = 3) -> list[dict]:
    """Return chunk dicts with elements, timestamps, shot breaks. TODO: Milestone 1."""
    raise NotImplementedError
