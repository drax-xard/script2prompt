"""H3 modes: instruction lines + section schemas per mode.

v1 mode is per-project (``chunk.mode_override`` is a v2 hook).
Exact wording comes from ``docs/H3_Prompting_Docs/`` (official Minimax guides).
"""
from __future__ import annotations

MODES = ("T2VA", "I2VA", "FL2VA", "L2VA", "R2V")

BASE_FIELDS = (
    "integrated_multimodal_description:",
    "overall_soundscape:",
    "non_diegetic_music:",
)
R2V_SECTIONS = (
    "subject_definitions:",
    "summary:",
    "retention_analysis:",
    "detailed_description:",
    "overall_soundscape:",
    "non_diegetic_music:",
)


def instruction_line(mode: str, final_shot: int = 1, duration: float = 8.0) -> str:
    """Render the mode's instruction line ("" for T2VA/R2V)."""
    if mode in ("T2VA", "R2V"):
        return ""
    if mode == "I2VA":
        return (
            "For the target video, at 0.00 seconds into the target video, "
            "<Picture 1> (from [Shot 1]) is fully referenced."
        )
    if mode == "FL2VA":
        return (
            "How the reference pictures align with the target video \u2014 "
            "Picture 1 (from Shot 1) aligns with the 0.00-second mark of the "
            f"target video; Picture 2 (from Shot {final_shot}) aligns with "
            f"the {duration:.2f}-second mark of the target video."
        )
    if mode == "L2VA":
        return (
            "How the reference pictures align with the target video \u2014 "
            f"<Picture 1> (from [Shot {final_shot}]) aligns with "
            f"the {duration:.2f}-second mark of the target video."
        )
    raise ValueError(f"unknown mode: {mode}")
