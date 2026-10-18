"""Single source of truth for the H3 prompt rules (v2 prerequisite).

Everything the prompt builders, the validator, the chunker, and Settings need
to agree on lives here once: modes and section labels, the camera and cut
vocabulary, language tags, retention markers, and the numeric budgets. Prose in
``prompts.py`` and the constants in ``validator.py`` are generated/derived from
these values so the two can no longer drift apart.

Sources: ``docs/H3_Prompting_Docs/`` (official Minimax guides) and the two
``Example_*_Prompt.txt`` files. Where the guides and examples differ, the
examples win (field labels on their own lines, style as a standalone sentence).
"""
from __future__ import annotations

# --- Modes and section schemas -------------------------------------------------

MODES = ("T2VA", "I2VA", "FL2VA", "L2VA", "R2V")
BASE_MODES = ("T2VA", "I2VA", "FL2VA", "L2VA")
KEYFRAME_MODES = ("I2VA", "FL2VA", "L2VA")

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

# --- Reference labels, language, markers --------------------------------------

REFERENCE_KINDS = ("Subject", "Picture", "Video", "Audio")
DEFAULT_LANGUAGE = "English"
# v1 detects only English; the language tag is still written inside <d>.
LANGUAGE_TAGS = (DEFAULT_LANGUAGE,)

# Ordered as the guides list them (used verbatim in prompts; membership-tested
# by the validator).
VISUAL_MARKERS = (
    "fully_preserved", "partially_preserved", "attribute_transfer", "weak_reference",
)
AUDIO_MARKERS = ("fully_copy", "partially_copy", "reference", "weak_reference")
TASK_TYPES = (
    "reference generation",
    "audio reference",
    "keyframe completion",
    "video editing",
    "video continuation",
    "audio reuse",
)

# --- Camera and cut vocabulary (guide §Camera) --------------------------------

CAMERA_MOTIONS = (
    "Zoom In", "Zoom Out", "Push In", "Pull Out", "Pan Left", "Pan Right",
    "Truck Left", "Truck Right", "Tilt Up", "Tilt Down", "Pedestal Up",
    "Pedestal Down", "Arc Shot", "Tracking Shot", "Static Shot", "Shake Slightly",
    "Shake Strongly", "POV", "Roll Clockwise", "Roll Counterclockwise",
)
CUT_VERBS = ("cuts to", "transitions to", "changes to", "switches to")

# --- Numeric budgets -----------------------------------------------------------

MIN_SECONDS = 5.0
CAP_SECONDS = 10.0
MAX_SHOTS = 3
CHAR_BUDGET = 7000
# Inclusive sentence ranges for the two audio fields.
SOUNDSCAPE_SENTENCES = (1, 4)
MUSIC_SENTENCES = (1, 3)
# Duration estimate: seconds per word for action and words per second of speech.
ACTION_WPS = 0.16
DIALOGUE_WPS = 2.75
