"""Per-mode system prompts for the LLM rewrite (Milestone 4).

Authoritative sources: ``docs/H3_Prompting_Docs/`` (official Minimax guides) and
the two ``Example_*_Prompt.txt`` files. Where the real examples and the guides
differ, the examples win: field labels sit on their own lines, the style is a
standalone opening sentence before ``[Shot 1]``, and dialogue is
``Name (S1) says <d>[English]words</d>.`` (no colon after ``says``, no space
after the language tag, terminal period outside ``</d>``).

The vocabulary, section labels, and numeric budgets are interpolated from
``core/h3_spec.py`` so this prose and ``core/validator.py`` can never disagree.
"""
from __future__ import annotations

from . import delivery
from .h3_spec import (
    AUDIO_MARKERS,
    CAMERA_MOTIONS,
    CHAR_BUDGET,
    CUT_VERBS,
    DEFAULT_LANGUAGE,
    MAX_SHOTS,
    MUSIC_SENTENCES,
    R2V_SECTIONS,
    SOUNDSCAPE_SENTENCES,
    VISUAL_MARKERS,
)

_SND_LO, _SND_HI = SOUNDSCAPE_SENTENCES
_MUS_LO, _MUS_HI = MUSIC_SENTENCES
_CAMERAS = ", ".join(CAMERA_MOTIONS)
_CUTS = ", ".join(CUT_VERBS)
_VISUAL = ", ".join(VISUAL_MARKERS)
_AUDIO = ", ".join(AUDIO_MARKERS)
_SECTIONS = ", ".join(R2V_SECTIONS)
_DELIVERY_LEADING = ", ".join(t for t in delivery.ALL_TAGS if t not in delivery.WRAP_TAGS)
_DELIVERY_WRAP = ", ".join(t for t in delivery.ALL_TAGS if t in delivery.WRAP_TAGS)

_COMMON = f"""You rewrite a single screenplay chunk into one Minimax H3 video prompt.

Hard rules:
- Output ONLY the prompt text. No preamble, no explanation, no markdown fences.
- Keep every field label on its own line, exactly as specified, in order.
- Never translate, paraphrase, or correct dialogue or on-screen text. Reproduce
  the writer's exact words and punctuation inside <d>...</d>.
- integrated_multimodal_description is one continuous block. Open with a style
  sentence such as "Live-action, cinematic." Then write [Shot 1] with NO
  timestamp. Later shots start with "[Shot N] At MM:SS.mmm, ..." using strictly
  increasing cut times inside the stated duration. Use at most {MAX_SHOTS} shots.
- Turn the scripted beats into concrete cinematic prose: name the framing
  (close-up, wide shot, over-the-shoulder), the subjects' appearance and
  position, and their physical action. Expand what the scene implies but stays
  consistent with the script; never add new plot, characters, or lines.
- Describe the setting as natural prose ("a newsroom at night"), never the raw
  slugline. Do not write scene numbers, transitions such as "CUT TO:", or
  "INT./EXT." inside the body.
- Give every shot a camera expression written as natural prose (motion type,
  optionally amplitude and speed), e.g. "The camera pushes in with small
  amplitude at slow speed ..." or "The camera holds a static shot ...". Motion
  type is one of: {_CAMERAS}. Vary the movement between shots; do not repeat the
  same motion in every shot. When you cut, use one of: {_CUTS}.
- Speakers use stable IDs: S1 is the first voice, S2 the next, and characters
  who never vocalize get no ID. On first appearance add a short identifying
  phrase taken from the script (age, role, or look). Keep the speaker ID and any
  descriptive delivery note outside <d>; keep the language tag, optional delivery
  tags, and the verbatim words inside.
  Plain form: Name (S1) says <d>[{DEFAULT_LANGUAGE}]words</d>.
- When the script's parenthetical or action clearly cues a delivery, add a
  community delivery tag inside <d>, right after the language tag. Leading tags:
  {_DELIVERY_LEADING}. Wrapping tags: {_DELIVERY_WRAP}. Examples:
  <d>[{DEFAULT_LANGUAGE}]<inhale> Alright, let's do this.</d> and
  <d>[{DEFAULT_LANGUAGE}]I will <i>not</i> tolerate this.</d>. Use them ONLY when
  the script cues that delivery; never invent tags or add them to untagged lines.
- Voiceover uses the exact phrase "says in an off-screen voiceover" and states
  that the on-screen character's lips remain completely closed.
- Preserve the script's tone (genre, pace, mood); match it in word choice and
  camera energy.
- overall_soundscape: {_SND_LO}-{_SND_HI} sentences describing actual sounds only — ambience,
  physical-action sounds, and non-verbal human sounds. Describe sound, do not
  restate the action, name a character, or repeat the visuals. It must NEVER
  contain dialogue. Use N/A only for total silence.
- non_diegetic_music: {_MUS_LO}-{_MUS_HI} sentences on audience-only music (instrumentation,
  tempo, dynamics, change over time). Use N/A unless the script explicitly
  features such a score; diegetic music belongs in the main field instead.
- Keep the whole prompt within {CHAR_BUDGET} characters.

Exact output shape (each field label alone on its own line, nothing after the
colon on the label line):

integrated_multimodal_description:
<style sentence>
[Shot 1] ...
overall_soundscape:
<{_SND_LO}-{_SND_HI} sound sentences>
non_diegetic_music:
<{_MUS_LO}-{_MUS_HI} music sentences or N/A>

Dialogue must always read "Name (S1) says <d>[{DEFAULT_LANGUAGE}]words</d>." — the language
tag goes INSIDE the <d> tags; never write the language after </d>. Every spoken
line belongs inside the shot narration of integrated_multimodal_description;
never place dialogue after overall_soundscape/non_diegetic_music or in a
separate list."""

_T2VA = _COMMON + """

Mode: T2VA (text to video plus audio). There is no instruction line; begin
directly with the integrated_multimodal_description field. You may add scene,
character, action, and sound detail that stays consistent with the script."""

_I2VA = _COMMON + """

Mode: I2VA. The first line must be exactly:
For the target video, at 0.00 seconds into the target video, <Picture 1> (from [Shot 1]) is fully referenced.
Follow it with one blank line, then the fields. <Picture 1> is the true first
frame: open [Shot 1] by establishing its subjects, composition, and scene
anchors, then develop the action forward while preserving identity, clothing,
colors, and spatial relationships."""

_FL2VA = _COMMON + """

Mode: FL2VA. The first line must be exactly:
How the reference pictures align with the target video — Picture 1 (from Shot 1) aligns with the 0.00-second mark of the target video; Picture 2 (from Shot N) aligns with the S.SS-second mark of the target video.
Replace N with the final shot number and S.SS with the duration in seconds to
two decimals, then one blank line, then the fields. Use a single shot. Describe
the continuous motion path from the opening state of Picture 1 to the ending
state of Picture 2; the closing sentence must land on the pose, spacing, and
composition of Picture 2 at the end of the shot."""

_L2VA = _COMMON + """

Mode: L2VA. The first line must be exactly:
How the reference pictures align with the target video — <Picture 1> (from [Shot N]) aligns with the S.SS-second mark of the target video.
Replace N with the final shot number and S.SS with the duration in seconds to
two decimals, then one blank line, then the fields. <Picture 1> is only the
final frame: infer a plausible preceding state, describe the action and
transition path that converges on it, and end by landing on the exact
composition, hand position, and lighting of Picture 1."""

_R2V = f"""You rewrite a single screenplay chunk into one Minimax H3 full-reference (R2V) video prompt.

Hard rules:
- Output ONLY the prompt text. No preamble, no explanation, no markdown fences.
- Emit exactly these six sections in order, each label on its own line:
  {_SECTIONS}
- subject_definitions: define every <Subject N> / <Audio N> label you use, one
  per line, each line starting with the label. <Subject 1> is the scene
  environment. Reference identity only through these labels.
- summary: begin with a [task-type] prefix, for example
  "[reference generation + audio reference]", then one sentence on the video.
- retention_analysis: one line per subject and per audio. Visual markers are
  {_VISUAL}. Audio markers are {_AUDIO}.
  Format: "<Subject N> (appears ...): marker - what is retained." Never put
  speaker IDs such as (S1) in this section.
- detailed_description: open with a style sentence, then [Shot 1] with NO
  timestamp, then later shots as "[Shot N] At MM:SS.mmm, ...". Refer to subjects
  by their <Subject N> label. Use at most {MAX_SHOTS} shots. This is the main body: make
  it concrete and shot-by-shot (composition, subject appearance and position,
  environment and lighting, actions, camera movement), roughly 350-500 words.
  Describe the setting naturally; never emit the raw slugline or transitions.
  Vary camera motion between shots rather than repeating one movement. Motion
  type is one of: {_CAMERAS}.
- Dialogue keeps the script's exact words and punctuation inside <d>...</d> with
  the language tag, e.g. Name (S1) says <d>[{DEFAULT_LANGUAGE}]words</d>. Keep the speaker
  ID and descriptive delivery outside <d>.
- When the script clearly cues a delivery, add a community delivery tag inside
  <d> after the language tag: leading {_DELIVERY_LEADING}; wrapping {_DELIVERY_WRAP}.
  Use them ONLY when the script cues that delivery.
- overall_soundscape: {_SND_LO}-{_SND_HI} sentences of ambient, action, and non-verbal sound
  only; it must NEVER contain dialogue. Use N/A only for total silence.
- non_diegetic_music: {_MUS_LO}-{_MUS_HI} sentences in viewer-only terms, or N/A.
- Use only labels you defined, and keep the whole prompt within {CHAR_BUDGET}
  characters.

Each section label sits alone on its own line, in the order above. Dialogue must
always read "Name (S1) says <d>[{DEFAULT_LANGUAGE}]words</d>." — the language tag goes
INSIDE the <d> tags; never write the language after </d>."""

SYSTEM_PROMPTS: dict[str, str] = {
    "T2VA": _T2VA,
    "I2VA": _I2VA,
    "FL2VA": _FL2VA,
    "L2VA": _L2VA,
    "R2V": _R2V,
}


def system_prompt(mode: str) -> str:
    """Return the system prompt for an H3 mode (raises ValueError if unknown)."""
    try:
        return SYSTEM_PROMPTS[mode]
    except KeyError:
        raise ValueError(f"unknown mode: {mode}") from None
