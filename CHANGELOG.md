# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

Versioning practices:
- Versions are `MAJOR.MINOR.PATCH` (e.g. `0.1.0`, `1.0.0`).
- `MAJOR`: incompatible API / prompt-output format changes.
- `MINOR`: new functionality in a backward-compatible manner (e.g. new parser, new H3 mode).
- `PATCH`: backward-compatible bug fixes and doc tweaks.
- Pre-`1.0.0` (`0.x.y`): API and output formats may change at any `MINOR` bump.
- Each release gets a dated section below with `Added / Changed / Fixed / Removed` entries
  and (once published) a version tag `vX.Y.Z` plus a GitHub release.

## [Unreleased]

## [0.9.1] - 2026-10-17

### Added
- Milestone 7 (polish): `pipeline.budgets` (per-chunk and project character/
  duration/shot usage) and `pipeline.lint` (validator issues aggregated with
  project-level warnings). CLI gains `--shots`, `--config`, `--strict`, plus a
  budget/lint summary; the web wizard gains budget meters and a lint panel.
- `README.md`: project overview, status, install/usage, config, layout, plus a
  first-time setup section for `install.sh`/`run_web.sh`.
- `run_web.sh`: checks the venv/`web` extra is installed before launching the
  Streamlit wizard.
- `install.sh`: creates the project venv and interactively installs the chosen
  optional extra (`none`/`pdf`/`web`/`both`, also as an argument).

### Changed
- `pipeline.run` clamps `duration` to the 5-10s range and `shots_max` to 1-3.

### Fixed
- `pyproject.toml`: pin setuptools package discovery to `script2prompt*` so
  editable installs no longer fail on flat-layout dirs (`out/`, `samples/`,
  `H3_Prompting_Docs/`).

## [0.9.0] - 2026-10-16

### Added
- `PROJECT_PLAN.md`: initial project plan (parsers, scene/chunk logic, character bible,
  multi-mode H3 support, web wizard, milestones).
- `H3_Prompting_Docs/`: local copies of the official Minimax H3 prompting guides
  (Text-and-Keyframe + Reference modes) used as the authoritative prompt spec.
- Scaffolding: `script2prompt/` package (parsers/core/app stubs), `pyproject.toml`,
  `config.toml`, `tests/` (stdlib unittest), `samples/sample_scene.txt`.
- `script2prompt/core/config.py`: stdlib `tomllib` loader with `config.local.toml`
  and `OPENAI_BASE_URL` / `S2P_MODEL` env overrides.
- `script2prompt/core/llm.py`: stdlib `urllib` chat-completions client (no `openai` SDK).
- Milestone 1 (offline core, T2VA): plain-text heuristic and Fountain-subset parsers
  (headings, cues with `(O.S.)` extensions, dialogue blocks, parentheticals,
  transitions); scene splitter with slugline context carry-over; character bible
  (speaker IDs in first-vocalization order, descriptions from `NAME (traits)`
  action intros, `None` IDs for non-vocal characters); chunker (duration estimate,
  greedy pack to target, <=10s, <=3 shots, `MM:SS.mmm` stamps, long-monologue
  split with `<scenetrans>` markers); deterministic T2VA template builder
  (`core/fallback.py` via `core/h3_builder.py`); T2VA validator (fields, shots,
  timestamps, `<d>` tags, soundscape/music budgets, 7000-char cap);
  `core/modes.py` instruction lines for all modes. 22 stdlib `unittest` tests,
  including end-to-end on `samples/sample_scene.txt`.
- T2VA template restyled to the real-example layout (`Example_Text2Video_Prompt.txt`):
  field labels on their own lines, standalone style sentence opening the body,
  dialogue as `Name (S1) says <d>[Lang]words</d>.` (no colon, no space after the
  language tag, period outside `</d>`). Conventions recorded in `AGENTS.md` and
  `PROJECT_PLAN.md` §2.1.
- Milestone 2 (keyframe modes): mode-specific `[Shot 1]` openings and landing
  sentences for I2VA (anchor `<Picture 1>` forward), FL2VA (single-shot path
  from Picture 1 to Picture 2) and L2VA (converge on `<Picture 1>` in the final
  shot); `chunk()` takes `mode` and forces single-shot chunks for FL2VA;
  validator checks instruction lines (without counting `[Shot N]` inside them),
  the blank line, and flags multi-shot FL2VA; `modes.py` gains section schemas.
- Milestone 4 (LLM wiring): `core/prompts.py` with per-mode system prompts for
  all five modes (`system_prompt()`, shared H3 rules + mode specifics);
  `core/llm.py` gains `messages()` (system prompt + structured chunk/bible brief,
  exact instruction line, R2V reference slots) and a working `rewrite()` with an
  injectable `chat_fn`; `h3_builder.build(..., rewrite=...)` uses the LLM when it
  returns non-empty text and falls back to the deterministic templates on error
  or empty output. 15 new tests (52 total), including a stdlib fake
  OpenAI-compatible server exercising `chat` round-trip and live `rewrite`.
- Milestone 5 (FDX + PDF parsers): `parsers/fdx.py` maps Final Draft
  `<Paragraph Type=...>` XML (via stdlib `xml.etree`) to elements, joining
  `<Text>` runs, reading only the script `<Content>` (title page ignored),
  skipping unknown types, and including dual-dialogue; `parsers/pdf.py`
  extracts text with lazily-imported `pypdf` and delegates to the plain-text
  parser (missing-extra error names `.[pdf]`); `parsers/__init__.py` adds
  `parse_file(path)` suffix dispatch. 8 new tests (60 total).
- Milestone 6 (wizard + export): `core/pipeline.py` end-to-end glue
  (`parse_bytes`, `run`, `characters_markdown`, `prompts_markdown`, `manifest`,
  `reference_manifest`, `export_pack`, `write_pack`); mode-aware reference
  slots (`ref_manifest.picture_slots` for I2VA/FL2VA/L2VA); `app/web.py`
  Streamlit wizard (upload → mode/settings → editable bible → generate/export;
  lazy `streamlit` import) and `script2prompt/__main__.py` CLI
  (`python -m script2prompt SCRIPT`, templates by default, `--llm` opt-in);
  `samples/one_page.txt` 1-page sample. 11 new tests (71 total) covering all
  five modes end-to-end plus export pack and CLI.

### Fixed
- Audit fixes: character bible no longer absorbs one-off ALL-CAPS words (TV/DAY/OK);
  bare action mentions join only on second mention, cue/intro names always join.
  Over-long single sentences now hard-split inside monologue chunking.
  `requires-python` corrected to `>=3.11` (`tomllib`); removed dead
  `[tool.unittest]` config; `PROJECT_PLAN.md` no longer mentions `pdfplumber`.
- Milestone 3 (R2V full-reference): `core/ref_manifest.py` proposes per-chunk
  Subject/Audio slots (Subject 1 environment, characters in bible order, one
  voice-timbre `<Audio N>` per speaker; pictures/videos empty placeholders);
  `core/r2v.py` builds the 6-section template with task-type prefix, valid
  retention markers, shot lists, and `<Subject N> (Sx)` speaker heads (no IDs in
  retention); validator checks section order, markers, task-type prefix, and
  true label definitions (line-start only). 7 new tests, 37 total.
- Audit fixes (R2V): numeric audio ordering (`S10` no longer sorts before `S2`);
  R2V `[Shot 1]` opening gains its missing camera sentence.
- Deep-audit hardening pass (B1–B13, B15 in `IMPROVEMENTS.md`). Chunker keeps a
  character cue atomic with its dialogue and re-emits the cue before split
  monologue continuations, so speaker IDs are never lost ("unseen speaker");
  the monologue threshold is derived from the 10s cap. Voiceover detection now
  reads extension and delivery independently (V.O. + parenthetical works) and no
  longer treats O.S./O.C. as voiceover. Plain-text parser: stricter sluglines
  (rejects `EXT.`-led dialogue, accepts mixed-case ` - TIME`, recognizes `EST.`),
  `FADE IN`/`FADE OUT`/`SMASH CUT` transitions, and cue lookahead so lone
  ALL-CAPS action beats are not characters. Character traits are captured
  mid-line (with a traits-like guard). CLI honors `--duration 0`; malformed
  `config.toml` raises a friendly `ValueError`; binary inputs are rejected;
  validator cross-checks speaker IDs against the bible and flags unseen
  speakers; `h3_builder.build` rejects scene dicts. 19 new regression tests
  (`tests/test_hardening.py`), 90 total.

### Changed
- Dependency policy: project-local `.venv/` only (git-ignored); zero required
  third-party deps for core (stdlib `dataclasses`, `tomllib`, `urllib`, `unittest`,
  `xml.etree`). Optionals are lazy-imported: `pdf` (`pypdf`, used by `parsers/pdf.py`
  only) and `web` (`streamlit`, used by `app/web.py` only). Dropped `pydantic`,
  `pyyaml`, `openai` SDK, `pytest`, `pdfplumber`, `fastapi/uvicorn`.
  See `PROJECT_PLAN.md` §3.2.
- Config format `config.yaml` → `config.toml` (stdlib `tomllib`).
  `PROJECT_PLAN.md` documents the dependency use policy (§3.2).

[Unreleased]: https://github.com/drax-xard/script2prompt/compare/v0.9.1...HEAD
[0.9.1]: https://github.com/drax-xard/script2prompt/releases/tag/v0.9.1
[0.9.0]: https://github.com/drax-xard/script2prompt/releases/tag/v0.9.0
