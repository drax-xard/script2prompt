# IMPROVEMENTS.md

Audit of the Script2Prompt codebase at commit `0d4271a` (Milestone 6 complete,
71 tests green). Method: full source re-read plus targeted fuzzing/probes of the
pipeline across all five modes and malformed inputs.

Severity: **High** = wrong output on common input, **Medium** = wrong output on
realistic input, **Low** = edge case / robustness / polish.

Status: **B1–B13 and B15 are fixed** (see `tests/test_hardening.py`, 19 new
regression tests). **B14** (compound speaker IDs) remains open as a feature.
The bug entries are kept as a record of the issue and the fix applied.

---

## Bugs

### B1 — [FIXED] High: chunker separates a character cue from its dialogue (speaker identity loss)

`script2prompt/core/chunker.py:131` (greedy flush) and
`script2prompt/core/chunker.py:44` (`_split_long_dialogue`).

The packer flushes when adding an element would exceed the target, but a
`character` cue and its `dialogue` are separate elements. For a single dialogue
line longer than ~20 words, the cue stays in the flushed chunk while the
dialogue starts the next one. The stranded cue chunk renders an empty extra shot;
the dialogue chunk has no cue and renders `An unseen speaker says <d>…</d>.`,
losing the `(S1)` identity. Long monologues have the same problem: only the first
≤18-word piece follows the cue, so every continuation piece is an "unseen
speaker".

Repro (one 24-word line):

```
INT. NEWSROOM - NIGHT

ELENA (40s, sharp editor) stands at the glass wall.

ELENA
I don't care who this burns, print the story tonight before the lawyers wake up and kill it.
```

Result: chunk 1 = `['action', 'character']` (dur 5.0, no dialogue); chunk 2 =
`['dialogue']` → `An unseen speaker says …`.

Fix idea: treat `character` + following `parenthetical`/`dialogue` as an atomic
block before packing, and/or carry the current speaker into split dialogue
pieces (or re-emit the cue) so continuation chunks keep the ID.

### B2 — [FIXED] Medium: monologue split threshold inconsistent with the 10s cap

`script2prompt/core/chunker.py:18` (`MONOLOGUE_WORDS = 30`) vs `CAP_SECONDS = 10`.

`estimate = words/2.75 + 1.0`, so the 10s cap fits ~24 words. Lines of 25–30
words are **not** split but overflow: e.g. a 30-word line yields a chunk clamped
to `10.0` whose speech needs ~11.9s. Fix: derive the threshold from the cap
(`int((CAP_SECONDS - 1.0) * 2.75)` ≈ 24) or split whenever a single element's
estimate exceeds the cap.

### B3 — [FIXED] Medium: voiceover detection fails when a delivery parenthetical is present

`script2prompt/core/fallback.py:31-33`. `_is_voiceover` concatenates extension and
delivery (`blob = ext + delivery`) then checks `"VOICEOVER" in blob or blob in
("OS","VO","OC")`. With `MARA (V.O.)` plus a `(softly)` parenthetical the blob is
`VOSOFTLY`, the check fails, and the required "says in an off-screen voiceover"
phrase and "lips remain completely closed" sentence are dropped.

```
INT. R - DAY

MARA (V.O.)
(softly)
I remember that road.
```

renders as a normal `says` line. Fix: inspect extension and delivery
independently.

### B4 — [FIXED] Medium: O.S./O.C. rendered as voiceover

`script2prompt/core/fallback.py:33` maps `OS`/`VO`/`OC` all to voiceover. The
guide reserves "says in an off-screen voiceover" (and the mandatory lips-closed
sentence) for V.O. A character who is present but off-screen (`O.S.`/`O.C.`) is
losing and re-opening their lips. Repro: `MARA (O.S.)` yields the voiceover
phrase + "lips remain completely closed". Fix: only V.O. (and maybe VO) is
voiceover; handle O.S./O.C. separately.

### B5 — [FIXED] Medium: a line starting with `INT.`/`EXT.` inside dialogue splits the scene

`script2prompt/parsers/plaintext.py:13,18`. `_is_heading` matches any line whose
stripped text starts with `INT`/`EXT` + `.`/`-`/`/`. A dialogue line like
`EXT. That's where I left it.` is reclassified as a heading and ends the scene.

```
INT. R - DAY

MARA
So you went to the old house.
EXT. That's where I left it.
And I never came back.
```

→ kinds `['heading','character','dialogue','heading','action']`. Fix: stricter
slugline pattern (require a location token, optional ` - TIME`) and/or suppress
heading matches while inside a dialogue block.

### B6 — [FIXED] Low/Medium: standalone ALL-CAPS action word becomes a character cue

`script2prompt/parsers/plaintext.py:39-53`. A short all-caps line that is really
an action beat (`THUNDER`, `SILENCE`, `A BEAT`) is parsed as a cue, creating a
phantom silent character in the bible (and thus in R2V `subject_definitions`).

```
INT. R - DAY

THUNDER

MARA
What was that?
```

→ bible `[('THUNDER', None, ''), ('MARA', 'S1', '')]`. Fix: require the next
non-blank line to be dialogue/parenthetical before accepting a cue (lookahead).

### B7 — [FIXED] Low: character traits only captured when the intro starts the action line

`script2prompt/core/characters.py:15,67`. `_ACTION_INTRO` is anchored with `^`, so
`Fluorescent lights hum. ELENA (40s, sharp editor) stands…` captures no
description. `samples/one_page.txt` already exhibits this (empty descriptions).
Fix: search anywhere in the action line with a guard against picking up
non-intro parentheticals.

### B8 — [FIXED] Low: `--duration 0` (or any falsy value) is silently ignored

`script2prompt/__main__.py:33`: `duration = args.duration or cfg[...]`. Use
`args.duration if args.duration is not None else cfg[...]` (and validate the
range, e.g. 5–10s).

### B9 — [FIXED] Low: malformed `config.toml` raises a raw `TOMLDecodeError`

`script2prompt/core/config.py:29`. Wrap the load with a friendly message naming
the file and line, consistent with the missing-extra error style.

### B10 — [FIXED] Low: binary/unknown files are read as text

`script2prompt/parsers/__init__.py:28`. Unknown extensions fall back to the
plain-text parser with `errors="replace"`, so a `.docx`/binary file produces
garbage elements. Detect NUL bytes / non-text and raise a clear "unsupported
format" error.

### B11 — [FIXED] Low: validator does not cross-check speaker IDs/names

`script2prompt/core/validator.py`. A prompt with `Bogus (S9) says …` passes
validation. Consider validating speaker IDs against the project bible (and
flagging names not in the bible) when a bible is available.

### B12 — [FIXED] Low: `FADE IN:` / `FADE OUT:` parsed as action

`script2prompt/parsers/plaintext.py` (transitions require `… TO:`). Common
screenplay openers become action lines. Add `FADE IN`/`FADE OUT`/`SMASH CUT` etc.

### B13 — [FIXED] Low: `EST.` sluglines not recognized

`script2prompt/parsers/plaintext.py:13`. `PROJECT_PLAN.md` §4.1 lists `EST.`.
Add it to the heading pattern.

### B14 — [OPEN] Low: compound speaker IDs (`S1,S2`) unsupported

The guide (§4.4) defines joint speakers; `characters.py`/`fallback.py` only
handle single IDs. Affects chorus/overlap lines.

### B15 — [FIXED] Low: `h3_builder.build` given a scene dict yields a degenerate prompt

Passing a scene (no `shots` key) instead of a chunk silently produces
`[Shot 1] ...`. Consider asserting on `shots` presence for a clearer failure.

---

## Improvements (robustness / design)

- **Shared soundscape picker.** `fallback.build` and `r2v.build` duplicate the
  "first two action sentences" logic (`fallback.py:173-183`, `r2v.py:105-115`).
  Extract one helper.
- **Narrow the broad `except Exception`** in `h3_builder.build`
  (`h3_builder.py:31`). It guarantees fallback but also swallows programming
  errors inside a custom `rewrite`. Catch expected network/parse errors and/or
  log the swallowed exception.
- **Harden `llm.chat`** (`llm.py:16`): `max_tokens`, configurable timeout, a
  retry/backoff, explicit non-2xx handling, and an env override for temperature.
  Currently a hung endpoint blocks for 120s per chunk.
- **Single source of truth for H3 rules.** The field/format rules are duplicated
  between `prompts.py` and `validator.py`; they can drift. Share constants.
- **`ref_manifest` environment naming.** Subject 1 reads `the INT. NEWSROOM -
  NIGHT environment`; parse the slugline into location/time for nicer
  definitions.
- **`title()` / `_CAPS_NAME`** mishandle hyphens and apostrophes
  (`MARY-JANE` → `Mary-jane`, `O'BRIEN` → `O'brien`; hyphen splits CAPS names).
- **Split long action lines.** Only dialogue is split; a 100-word action beat is
  clamped to a 10s chunk. Split action at sentence boundaries like monologues.
- **Min-duration behavior.** Any tiny chunk is padded to 5s
  (`chunker.py:90`); two one-line beats become 10s of runtime. Consider the
  floor only when content justifies it.
- **Package metadata.** Add `[project.scripts]` (`script2prompt = "script2prompt.__main__:main"`),
  project URLs, and classifiers to `pyproject.toml`.
- **Manifest versioning.** Add `schema_version` to `manifest.json` /
  `reference_manifest.json` for forward compatibility.
- **`write_pack` overwrite/clean option** and return a manifest of written files.
- **`web.py` testability.** It is untestable without Streamlit installed; move
  bible-editing and pack assembly into `pipeline`/pure helpers and cache the
  parsed file across reruns.
- **`plaintext` inline headings.** Also consider that `plaintext` cannot
  currently distinguish a slugline from dialogue without dialogue-state context.

---

## Test gaps

Addressed by `tests/test_hardening.py` (19 tests) for B1–B13/B15. Still open:

- No test for `llm.chat` error paths (non-2xx, malformed JSON) — only the
  success path against the fake server.

## Tooling / repo hygiene

- **No CI.** Add GitHub Actions running `.venv/bin/python -m unittest discover -s tests`
  on 3.11–3.13, plus a zero-dependency import check and an optional-extras job.
- **No `LICENSE`.** Recommended for a public repo.
- **No `README.md`.** AGENTS.md forbids unprompted doc files, so this is only a
  recommendation; a short README pointing at the CLI and `PROJECT_PLAN.md` would
  help first-time users.
- **No linter config.** `ruff`/`flake8` would catch the unused-import/dead-code
  class of issues (none found by hand, but it is unenforced).

---

## Suggested fix order

1. **B1** (High) + regression test — it silently corrupts common scripts. **Done.**
2. **B2, B3, B4** (Medium) + tests. **Done.**
3. **B5, B6, B7, B12, B13** (parser correctness). **Done.**
4. **B8, B9, B10, B11, B15** (robustness). **Done.**
5. Improvements (shared helpers, `llm.chat` hardening, metadata) and CI. **Open.**
6. **B14** (compound speaker IDs). **Open** (feature, not a defect).
