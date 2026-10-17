# IMPROVEMENTS.md

Audit of the Script2Prompt codebase at commit `0d4271a` (Milestone 6 complete,
71 tests green). Method: full source re-read plus targeted fuzzing/probes of the
pipeline across all five modes and malformed inputs.

Severity: **High** = wrong output on common input, **Medium** = wrong output on
realistic input, **Low** = edge case / robustness / polish.

Status: **B1–B15 are fixed** (see `tests/test_hardening.py`, plus the 0.10.x
regression tests). **B14** (compound speaker IDs) landed as a feature. The bug
entries are kept as a record of the issue and the fix applied.

The 0.10.0 milestone (see `CHANGELOG.md`) also resolved several items from the
"Improvements" list below (shared soundscape helper, `llm.chat` hardening,
environment naming, name casing, long-action splitting, tiny-chunk merging);
those entries are marked **[DONE 0.10.0]**.

For the forward-looking, post-v1 plan (Project Manager, ComfyUI, Settings,
desktop bundle, built-in LLM), see **Post-v1 roadmap (v2)** near the end.

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

### B14 — [FIXED] Low: compound speaker IDs (`S1,S2`) unsupported

The guide (§4.4) defines joint speakers; `characters.py`/`fallback.py` only
handled single IDs. Affected chorus/overlap lines.

Fix: `characters.split_joint` splits a joint cue (`ELENA AND MARA`, also `&`,
`/`, `+`) into individual names, which `build_bible` registers as separate
characters (each with its own `Sx`) and `_make_chunk` records as speakers. The
renderers emit a compound head — `Elena and Mara (S1,S2) say <d>…</d>.` for the
base modes and `<Subject 1> and <Subject 2> (S1,S2)` for R2V — and
`validator._check_speakers` now validates every ID in the group.

### B15 — [FIXED] Low: `h3_builder.build` given a scene dict yields a degenerate prompt

Passing a scene (no `shots` key) instead of a chunk silently produces
`[Shot 1] ...`. Consider asserting on `shots` presence for a clearer failure.

### B16 — [FIXED] Medium: a leading UTF-8 BOM corrupts the first line

`parsers/__init__.py` decoded with `errors="replace"` but never stripped a byte
order mark, so a `.txt`/`.fountain` saved with a BOM had `\ufeff` glued to the
first line — the opening slugline parsed as `action` and the scene lost its
context.

Fix: decode with `utf-8-sig`, which drops a leading BOM and otherwise behaves
like `utf-8`.

### B17 — [FIXED] Medium: R2V prompt for a wordless cold open had no subjects

A chunk with no slugline and no characters (e.g. a wordless cold-open action
beat) produced an empty `subject_definitions:` section, which the validator
rejects (`defines no reference labels`).

Fix: `ref_manifest.propose` synthesizes a placeholder `<Subject 1>` environment
subject when nothing else is present, so the section is always well-formed.

### B18 — [FIXED] Medium: voiceover missed when the cue had a second parenthetical

`fallback._is_voiceover` stripped non-letters from the *whole* extension, so
`MARA (V.O.) (CONT'D)` normalized to `VOCONTD` and no longer matched `VO` —
the line was rendered as ordinary on-screen speech.

Fix: normalize each parenthetical independently and test each token, so `(V.O.)`
combined with `(CONT'D)`/`(O.S.)` still reads as a voiceover.

### B19 — [FIXED] Medium: joint action intro / all-caps mention created phantom characters

`MARA AND LEO (30s) enter together.` registered a single phantom character
`MARA AND LEO` (and lost MARA/LEO's traits), and an all-caps action mention like
`The ELENA AND MARA team…` produced a phantom `ELENA AND`.

Fix: `_ACTION_INTRO` accepts `AND`/`&` connectors and the intro is split with
`split_joint` (each part registered with the shared traits); `_CAPS_NAME` will
not swallow connector words and `AND`/`OR`/`THE`/`A`/`AN` were added to `_NOISE`.

### B20 — [FIXED] Low: `title()` mangled alphanumeric designators

`C3PO` was titled `C3Po` because every alphabetic run was capitalized.

Fix: `title()` leaves a letter run untouched when it touches a digit (`C3PO`,
`R2D2` stay as written) while `MARY-JANE`/`O'BRIEN` still title-case.

### B21 — [FIXED] Low: Fountain parser ignored dialogue state for headings

Unlike `plaintext`, `fountain.py` still treated a slugline-looking line inside a
dialogue block as a new heading. Fix: apply the same `not in_dialogue` guards
(and exclude `_is_heading` lines from the cue check) so both parsers agree.

### B22 — [FIXED] Low: invalid numeric env override raised a raw `ValueError`

`S2P_TEMPERATURE=hot` produced a bare `could not convert string to float`. Fix:
a helper wraps parsing with `invalid S2P_TEMPERATURE: 'hot' (expected a number)`.

### B23 — [FIXED] Low: `pipeline.reference_manifest` raised for T2VA

Calling it for a T2VA project raised `ValueError: no picture slots for mode:
T2VA` (only `export_pack` guarded the call). Fix: T2VA now returns an empty
checklist (`chunks: []`) instead of raising.

### B24 — [FIXED] Low: R2V empty style produced a double space

`r2v.build(style="")` emitted `uses a  style`. Fix: blank styles fall back to
`Live-action, cinematic` after whitespace normalization.

### B25 — [FIXED] Low (docs): `.spmd` documented as plain-text

`parsers/__init__.py` maps `.spmd` to the Fountain parser (Fountain's original
"Screenplay Markdown" extension), but `TESTING.md` listed it as plain-text. Fix:
docs now group `.spmd` with `.fountain`.

---

## Improvements (robustness / design)

- **[DONE 0.10.0] Shared soundscape picker.** Extracted to
  `render.soundscape_sentences`, used by `fallback.build` and `r2v.build`.
- **[DONE 0.10.0] Narrow the broad `except Exception`** in `h3_builder.build`:
  now catches only `llm.LLMError`, so programming errors propagate.
- **[DONE 0.10.0] Harden `llm.chat`**: `LLMError`, `max_tokens`, configurable
  timeout, retry/backoff, explicit non-2xx handling, and `S2P_TEMPERATURE` /
  `S2P_TIMEOUT` env overrides.
- **Single source of truth for H3 rules** (deferred): the field/format rules in
  `prompts.py` (prose) and `validator.py` (constants) can still drift.
- **[DONE 0.10.0] `ref_manifest` environment naming.** `slugline_parts` parses
  location/time ("Newsroom at night").
- **[DONE 0.10.0] `title()` / `_CAPS_NAME`** handle hyphens and apostrophes
  (`Mary-Jane`, `O'Brien`).
- **[DONE 0.10.0] Split long action lines** at sentence boundaries like
  monologues (`chunker._split_long_action`).
- **[DONE 0.10.0] Min-duration behavior.** A sub-5s trailing chunk merges into
  its predecessor when the pair fits the cap; the 5s floor applies only to a
  chunk that stands alone.
- **[DONE 0.10.x] Package metadata.** `[project.scripts]`
  (`script2prompt = "script2prompt.__main__:main"`), project URLs, readme,
  keywords, and Python 3.11–3.14 classifiers added to `pyproject.toml`.
- **[DONE 0.10.x] Manifest versioning.** `manifest.json` /
  `reference_manifest.json` stamp `schema_version` (`pipeline.SCHEMA_VERSION`),
  with `migrate_artifact`/`load_artifact` for forward-compatible loading.
- **[DONE 0.10.x] `write_pack` clean/overwrite option** (`clean=True`, CLI
  `--clean`) and it returns the list of written files.
- **`web.py` testability** (still open; a v2 prerequisite). It is untestable
  without Streamlit installed; move bible-editing and pack assembly into
  `pipeline`/pure helpers and cache the parsed file across reruns.
- **[DONE 0.10.x] `plaintext` inline headings.** A slugline-looking line inside
  a dialogue block is now kept as dialogue using dialogue-state context.

---

## Test gaps

Addressed by `tests/test_hardening.py` (B1–B22 regression tests, including B14
joint speakers and B16–B24 audit fixes), `tests/test_parsers.py` (B16/B21), and
`tests/test_quality.py` + `tests/test_llm.py` for the 0.10.0 work. `write_pack`
clean/overwrite semantics and the T2VA empty reference manifest (B23) are covered
in `tests/test_pipeline.py`. No known open gaps.

## Tooling / repo hygiene

- **[DONE 0.10.x] CI.** `.github/workflows/ci.yml` runs
  `.venv/bin/python -m unittest discover -s tests` on Python 3.11–3.14, plus a
  zero-dependency import check and an optional-extras job (pdf/web/dev + ruff).
- **[DONE 0.10.0] `LICENSE`** — GPL-3.0-or-later.
- **[DONE] `README.md`** — project overview, install/usage, config, layout.
- **[DONE 0.10.0] Linter config** — `ruff` via the `dev` extra + `[tool.ruff]`.

---

## Suggested fix order

1. **B1** (High) + regression test — it silently corrupts common scripts. **Done.**
2. **B2, B3, B4** (Medium) + tests. **Done.**
3. **B5, B6, B7, B12, B13** (parser correctness). **Done.**
4. **B8, B9, B10, B11, B15** (robustness). **Done.**
5. Improvements (shared helpers, `llm.chat` hardening, output quality). **Done (0.10.0).**
   CI + package metadata (scripts/URLs) **done (0.10.x)**.
6. **B14** (compound speaker IDs). **Done (0.10.x)**.
7. **B16–B25** (second deep audit: BOM, empty R2V subjects, voiceover
   parentheticals, phantom joint names, `title()` designators, Fountain dialogue
   state, env-error message, T2VA reference manifest, empty style, `.spmd`
   docs). **Done.**

---

## Post-v1 roadmap (v2)

Forward-looking design record. Nothing here is implemented yet; it captures the
agreed direction after the v1 audit. v1 = `0.10.0` and prior.

### Decisions (locked)

1. **Audience first:** power users already running their own ComfyUI and a
   `llama.cpp`-compatible server. One-click/non-technical packaging is a later
   concern, after the framework stabilizes.
2. **Generation backend:** target **ComfyUI's** HTTP pipeline directly.
3. **Dependency stance:** the zero-required-deps core stays the *default*, but it
   is a directive ("avoid dependency abuse"), **not a fanatical hard rule**. A
   `1.0` "desktop bundle" that ships heavier optionals is acceptable.
4. **Scope order:** Project Manager → ComfyUI → everything else
   (Settings/Options, desktop bundle, built-in LLM).
5. **Project persistence:** the Project Manager stores the **raw source inside the
   bundle** (portable, heavier) — not just a path + hash reference.

### Prerequisites (do before v2 features)

The moment state is persisted, these become load-bearing; both are already
flagged above.

- **[DONE for `manifest.json` / `reference_manifest.json`]** `schema_version`
  with forward-compatible loaders and migrations (`pipeline.SCHEMA_VERSION`,
  `migrate_artifact`, `load_artifact`). The project file will reuse the same
  helper. (`IMPROVEMENTS.md` "Improvements".)
- **Single source of truth for H3 rules** — extract a `core/h3_spec.py` holding
  the camera vocabulary, cut verbs, language tags, section labels, retention
  markers, budgets (5–10s, ≤3 shots, 7000-char cap). Kills the drift risk between
  `core/prompts.py` (prose) and `core/validator.py` (constants); Settings can
  display it read-only and gate overrides.
- **Stable chunk IDs** — `"{scene_index}:{first_element_index}-{last_element_index}"`
  so manual edits survive re-parse; a source-hash change marks stale chunks
  instead of discarding work.
- **Testable state layer** — all Project Manager / library / ComfyUI logic lives
  in `core/` (stdlib `unittest`), never in `app/web.py` (currently untestable
  without Streamlit).

---

### 1. Project Manager — **priority 1**

**Problem.** `pipeline.run()` (`core/pipeline.py:57`) is a one-shot pure function;
its result only lives in `st.session_state` (`app/web.py:87`), keyed by a file
fingerprint. A 120-page script is ~100–150 scenes and **well over 1000 chunks** —
no persistence, no resumability, no edits that survive a rerun.

**Shape.** New UI-agnostic `core/workspace.py` + `core/library.py`, UI on top.
Persistence uses stdlib `json` + `zipfile` (single `.s2p` bundle), so it does not
violate the dependency stance.

**Data model.** Project = directory or single `.s2p` zip:

- `project.json` — `schema_version`, meta, embedded `source/` (raw script +
  `sha256` + format), settings, status rollups.
- `bible/characters.json` — extend `Character` (`core/characters.py:21`) with
  voice description, aliases, reference image/audio paths, per-scene appearance.
- `bible/locations.json` — the Setting/Location bible (below).
- `bible/props.json` — `<Subject N>` objects, `<Video N>` sources (R2V slots
  already exist in `core/ref_manifest.py`).
- `bible/palettes.json` — Color Palette presets.
- `bible/continuity.json` — costumes, injuries, weather, time progression.
- `chunks/NNN.json` — `{stable_id, scene, element_range, mode_override, status,
  prompt, prompt_history[], issues[], references{}, generation{}}`.
- `assets/` — imported reference images/audio, or pointers into a global library.

**Features required to be *great*, not merely "save/load":**

- **Deterministic re-parse + diff.** Re-parse the embedded source on load and
  diff against stored chunks; stable IDs preserve edits; source-hash change flags
  stale chunks.
- **Per-chunk lifecycle:** `draft → edited → approved → exported → generated`.
  Regenerate only *dirty* chunks — the key to 1000-chunk tractability.
- **Revision history per chunk** with A/B variants and revert; record origin
  (`template` / `llm` / `manual` / `llm-retry`) on each revision.
- **Autosave + crash recovery.**
- **Location bible (high value).** Reuse `ref_manifest.slugline_parts()`
  (`core/ref_manifest.py:26`) and the scene `context` from `core/scenes.py:`;
  map `INT. WAREHOUSE` → canonical entity (description, style notes, reference
  images, time-of-day variants) and inject its description as the environment
  block (the R2V `<Subject 1>` path at `ref_manifest.py:98`). This is exactly the
  "parser logically replaces EXT/INT sections with the appropriate descriptions"
  goal.
- **Prop/object bible** — completes R2V subjects.
- **Continuity bible** — gives the chunker's continuity carry-over a home.
- **Aliases/nicknames** — `Bobby`/`ROBERT`/`Bob` collapse to one subject so the
  bible and speaker IDs do not fragment.
- **Cross-project library** (`~/.config/script2prompt/library/`) — reusable
  characters, locations, palettes, voices, and (later) ComfyUI workflow
  templates; enables a consistent "universe".
- **Per-scene/per-context overrides** — this is the reserved
  `chunk.mode_override` v2 hook (`PROJECT_PLAN.md:13`, `AGENTS.md:43`): different
  modes/params for a dialogue scene vs. an action montage without locking the
  whole project to one mode.
- **Named strategies/presets** — bundles of (mode, duration, shots, style,
  palette, chunking) applied per scene or project-wide.
- **Search/filter** by character, location, status, lint warning, over-budget.
- **Dashboard** — total runtime estimate, budget coverage, reference-asset
  completion checklist, unapproved-chunk count.
- **Batch ops** — regenerate all warning/over-budget chunks; apply a global style
  change while *locking* approved chunks; promote a draft strategy.
- **Color Palette presets.** H3 has no negative prompts and style is a standalone
  opening sentence, so palettes are *textual* preset descriptions
  (`TEAL/ORANGE`, `DESATURATED KODAK`) named, saved, and composed into the style
  sentence.

**Effort:** L–XL. **Priority: 1.**

---

### 2. ComfyUI integration — **priority 2**

**Goal.** Close the loop from generated prompt → rendered video, and make the
reference manifest concrete. ComfyUI exposes an HTTP API (`/prompt`, `/queue`,
`/history/{id}`, `/view`, `/upload/image`); workflows are JSON graphs. Integrate
with stdlib `urllib` (mirror `core/llm.py`), **no new hard dependency**.

- **`core/comfy.py`** (optional, off by default): `comfyui.base_url`; submit one
  prompt per approved chunk; poll for completion; fetch output via `/view`.
- **Robust placeholder convention** — never hardcode node IDs (they drift with
  custom nodes). Mark the input node (e.g. `_meta.title == "S2P_PROMPT"`) and
  substitute the prompt; validate the workflow before submit; provide an
  import/mapping UI.
- **Reference substitution** — upload/link the concrete slots already emitted by
  `ref_manifest.picture_slots` / `propose` (I2VA/FL2VA/L2VA images, R2V
  subject/picture/video/audio) via `/upload/image`. The reference manifest stops
  being a checklist and becomes real inputs; the Project Manager asset library
  supplies the bytes.
- **Two quality tiers** — model "draft" (few steps, low res, short) and
  "production" (full steps/res) as **two workflow templates** plus a per-run
  toggle. Approve a draft, then promote the same chunk to production. (Just two
  JSONs + parameters.)
- **Batch/queue** — enqueue the full approved set for an overnight draft pass;
  monitor, cancel, retry per chunk.
- **Provenance & iteration loop** — store seed, workflow hash, model, prompt
  hash, and output per generation; land results back in the Project Manager as
  per-chunk previews. This closes the draft → review → production loop with #1.

**Effort:** M–L. **Priority: 2.**

---

### 3. Settings/Options page — priority 3

Low-risk, high-value; pairs with #1.

- **Layered precedence, surfaced in the UI:** built-in defaults < global user
  config < project config < per-session. Today: `config.toml` <
  `config.local.toml` < env (`core/config.py:26`); extend to include the project
  file.
- **Validation + ranges** (`duration` 5–10, `shots` 1–3, temperature bounds);
  some already clamped in `pipeline.run` (`core/pipeline.py:61`).
- **"Test connection"** button echoing model/latency from the OpenAI-compatible
  endpoint (`core/llm.py`), plus a clear offline-fallback indicator.
- **Secrets discipline** — keys come from **env only**, never persisted in
  project files. (Only `base_url` exists today; keep it that way.)
- **H3 tag/video definitions** — expose `core/h3_spec.py` **read-only**, with
  advanced overrides gated behind a warning (free-editing tags can invalidate
  `core/validator.py`).
- Export/import settings; reset to defaults.

**Effort:** M.

---

### 4. Desktop bundle — priority 4

The target "own window, no browser dependency" is only *fully* satisfiable by
bundling Chromium, which we will **not** do.

| Option | Deps | Own window? | Verdict |
|---|---|---|---|
| As-is | none | no (system browser) | Zero cost; works via `run_web.sh` |
| **`pywebview`** | optional `desktop` extra | yes | **Recommended** — wraps OS WebView (WebKitGTK / Edge WebView2 / WKWebView); still needs `webkit2gtk` on Linux |
| Bundled Chromium (CEF / Qt WebEngine) | 100s of MB, per-OS, Qt licensing | yes | **Rejected** — "dependency abuse" |
| stdlib `webbrowser.open()` | none | "sort of" | Trivial auto-open; degrades to default browser |
| stdlib `http.server` + hand-rolled HTML/JS | none | via pywebview | Principled, enables a true zero-Streamlit desktop app — but rewrites `app/web.py` (XL) |
| Electron/Tauri | non-Python | yes | Out of scope |

**Plan:** add `pywebview` as an optional `desktop` extra (lazy import, same
pattern as `streamlit`) with automatic fallback to `webbrowser` /
`streamlit run`. Optionally plan the stdlib-server rewrite for `1.0`, which also
removes Streamlit's telemetry and testability drawbacks. Be explicit to users:
WebView wrappers are *not* more compatible than a browser.

**Effort:** S (pywebview wiring) / XL (stdlib-server rewrite). Ships with `1.0`.

---

### 5. Built-in LLM inference engine — priority 5

Keep the current OpenAI-compatible HTTP path (`core/llm.py`) as the **primary**
path. If a "built-in" engine is wanted:

| Option | Verdict |
|---|---|
| **Bundle `llama-server` as a managed sidecar** | **Recommended** — reuses `core/llm.py` **unchanged** (OpenAI-compatible), any GGUF, GPU handled by the binary, clean process boundary. Do **not** bundle weights; download on demand with checksum |
| `llama-cpp-python` (in-process GGUF) | Risky — native build (CMake/compiler), per-platform wheels, GPU special indexes |
| `ctransformers` | Avoid (unmaintained) |
| `transformers`/torch | Avoid (multi-GB stack) |
| Managed Ollama sidecar | Fine stopgap |

Settings panel: start/stop, model selection, GPU offload/context. Set
expectations: chunk rewriting is short-prose work, so a 7B-Q4 model is ample —
this is a *convenience*, not a quality upgrade over a running server.

**Effort:** M (sidecar manager) / L (packaging).

---

### Later (not v2): story/book → screenplay

Turn a non-screenplay story/book into an industry-standard screenplay using a
parser + LLM, then feed that screenplay into the existing Script2Prompt pipeline —
offering an end-to-end "prose → audiovisual product" flow. Explicitly **out of
scope for v2**; recorded here only as a direction. Revisit once the Project
Manager and ComfyUI loop are stable.

---

### Sequencing summary

1. Prereqs: `schema_version`, stable chunk IDs, `core/h3_spec.py`, testable
   state layer.
2. **Project Manager** (core persistence + per-chunk state + layered bibles).
3. **ComfyUI** (workflow templates, reference substitution, draft/production
   queue).
4. **Settings/Options** page.
5. **Desktop bundle** at `1.0` (`pywebview` extra; optional stdlib-server
   rewrite).
6. **Built-in LLM** (`llama-server` sidecar).
7. Later: story/book → screenplay.

### Risks

- **Project Manager** — state-management complexity and schema migrations; ship
  `schema_version` from day one.
- **ComfyUI** — workflow JSON drift across custom-node/version changes; mitigate
  with the `_meta.title` placeholder convention and pre-submit validation.
- **Desktop/LLM** — packaging per-OS (WebView deps, GPU binaries, model size);
  keep off by default and download on demand.
- **Release model** — #4/#5 turn this into a distributed desktop app and likely
  warrant a `1.0` milestone (today `releases/*.zip` is source-only).
