# next-steps.md

Handoff / starting point for the next work session. This is a working notes file,
not a design doc — the v2 design lives in [`IMPROVEMENTS.md`](IMPROVEMENTS.md)
§ *Post-v1 roadmap (v2)*. Keep this file short-lived: delete entries as they land.

## Status snapshot (verified)

- Version **`0.11.1`** (`pyproject.toml`), pre-1.0.
- Tests: **153 green** — `.venv/bin/python -m unittest discover -s tests`.
- Lint: **clean** — `.venv/bin/ruff check .`.
- venv Python: **3.14.4**; `requires-python = ">=3.11"`.
- Working tree **clean** at `cd61033` (branding/docs commits). **No commits
  unless the user asks.**
- `out/`, `releases/`, `*.zip`, `.venv/`, `config.local.toml` are git-ignored.

## Working agreements (from `AGENTS.md`)

- Everything runs through `.venv/bin/python` / `.venv/bin/pip`. Never bare `pip`,
  never `--system`, never `sudo`.
- Core has **zero required third-party deps**; optionals are lazy-imported
  inside functions and their missing-extra errors must name the exact install
  command.
- Stdlib `unittest` (not pytest); no pytest config in `pyproject.toml`.
- Read `H3_Prompting_Docs/` + `PROJECT_PLAN.md` §2 before touching `modes.py`,
  `h3_builder.py`, `validator.py`.
- Record behavior/dependency changes in `CHANGELOG.md` under `Unreleased`.
- No commits unless asked. Don't create `*.md` unprompted.

---

## SESSION FOCUS — Output quality (current)

Goal: raise the quality of the actual generated H3 prompts on **both** paths —
the LLM rewrite (primary) and the deterministic templates (offline) — plus the
inputs that feed them. Verifiable offline (unittest) and A/B'd live.

### Live LLM endpoint (user-provided)

- Base URL: `http://127.0.0.1:5001/v1` (koboldcpp; `/v1/models` OK, model loaded).
- Model: `koboldcpp/Qwen3.5-9B-Uncensored-HauhauCS-Aggressive-Q6_K`.
- Run with env only (never commit keys/paths):
  ```bash
  OPENAI_BASE_URL=http://127.0.0.1:5001/v1 \
  S2P_MODEL=koboldcpp/Qwen3.5-9B-Uncensored-HauhauCS-Aggressive-Q6_K \
  .venv/bin/python -m script2prompt samples/one_page.txt --llm -o out_ab
  ```

### Confirmed output problems (from current `out/`)

- **Template:** identical boilerplate every chunk (`A medium-wide shot frames the
  scene. The scene takes place at INT. NEWSROOM - NIGHT. The camera pushes in…`);
  raw sluglines in prose; later shots always `cuts to a new angle… holds a static
  shot`; `overall_soundscape` **copies action text verbatim** (not sounds; can
  include character intros); `non_diegetic_music` always `N/A`; no camera variety.
- **LLM:** the user brief (`llm._user_content`) omits overall tone, neighbor-chunk
  continuity, anti-repetition, and soundscape-must-not-duplicate guidance; each
  chunk is rewritten in isolation; validator issues are never fed back.
- **Input:** descriptions come only from one `NAME (traits)` intro; slugline stays
  raw in prose.

### Plan (phased)

1. **`core/render.py` shared primitives**
   - `scene_phrase(context)` → naturalized setting via `ref_manifest.slugline_parts`
     (`INT. NEWSROOM - NIGHT` → `a newsroom at night`; article-correct; never raw).
   - `camera_sentence(...)` → content-aware, varied per shot (establishing /
     dialogue / action), deterministic from context+shot index.
   - `soundscape_sentences(chunk)` → rewrite: location/time ambience + small,
     conservative verb/noun→sound lexicon; never verbatim action, names, or dialogue.
   - `music_line(...)` → always `N/A` unless the script explicitly references music.
2. **`core/fallback.py`, `core/r2v.py`** — naturalized setting, varied shot
   openings, drop `The scene takes place at INT. …` boilerplate; de-formulaic R2V
   `summary`/`retention_analysis`/`subject_definitions`. Preserve the style line
   and speaker-head formats the tests pin (`Mara, 30s, tired barista (S1) says
   <d>…</d>.`).
3. **`core/characters.py`** — guarded description enrichment (incl. comma
   appositive `MARA, a tired barista`), keep anti-phantom-name guards; surface a
   voice/timbre note for R2V `<Audio N>`.
4. **`core/prompts.py`, `core/llm.py`, `core/h3_builder.py`** — stronger system
   prompts (soundscape = sounds only; music rules; camera variety; no stage
   directions/meta; naturalized setting; preserve tone); richer user brief with an
   **optional per-project context call** (logline/tone/genre/palette/voice notes),
   naturalized scene, neighbor-chunk continuity, anti-repetition, first-appearance
   identification; **validate→repair loop** (`llm.fix_attempts`, default 1) feeding
   validator issues back, then template fallback. `LLMError`/disabled context
   degrade gracefully. Per-project call stays inside `--llm` opt-in.
5. **Tests + docs** — new `tests/test_output_quality.py` (body has no raw
   `INT./EXT.`; soundscape never duplicates action and has no `(S1)`/names;
   multi-shot camera variety; music `N/A` by default); update only tests that
   legitimately pin changed prose; `CHANGELOG.md` `Unreleased`.

### Decisions locked this session

- Include the optional per-project context call (one extra LLM call per project).
- Music: keep `N/A` unless the script explicitly mentions music.

---

## A. Loose ends — ✅ DONE (committed at `cd61033`)

- [x] Doc test-count drift, stale fallback error message, dependency-stance docs,
      package metadata, CI, `write_pack --clean`, B14 joint speakers, inline
      heading nuance.
- [ ] **Secrets discipline (note, not code yet).** If remote OpenAI-compatible
      endpoints are ever supported, keys come from **env only** — never persisted
      in project files. Today only `base_url` exists; keep it that way.

## B. Prerequisites blocking v2 (do before Project Manager work)

These are load-bearing the moment state is persisted (see `IMPROVEMENTS.md`
§ *Prerequisites*):

- [x] **`schema_version`** (`pipeline.SCHEMA_VERSION`) on `manifest.json` /
      `reference_manifest.json`, with `migrate_artifact`/`load_artifact`
      forward-compatible loading.
- [ ] **`core/h3_spec.py` — single source of truth for H3 rules** (camera vocab,
      cut verbs, language tags, section labels, retention markers, budgets:
      5–10s, ≤3 shots, 7000-char cap). **This may be partly realized by the
      render primitives above — reconcile when done.**
- [ ] **Stable chunk IDs** — `"{scene_index}:{first_element_index}-{last_element_index}"`.
- [ ] **Testable state layer.** Move bible-editing and pack assembly out of
      `app/web.py` into `core/`.

## C. Then the v2 roadmap (locked scope order)

Full detail in `IMPROVEMENTS.md` § *Post-v1 roadmap (v2)*:

1. **Project Manager** — persisted, chunk-addressable `.s2p` bundles (raw source
   embedded), per-chunk lifecycle, layered bibles, strategies/presets, library.
2. **ComfyUI integration** — stdlib `urllib` client, `_meta.title` placeholder
   convention, reference-slot substitution, draft/production tiers, provenance.
3. **Settings/Options page** — layered precedence, validation/ranges, "test
   connection", read-only `h3_spec`.
4. **Desktop bundle** at `1.0` — `pywebview` optional `desktop` extra; optional
   stdlib-`http.server` rewrite to drop Streamlit.
5. **Built-in LLM** — managed `llama-server` sidecar (reuses `core/llm.py`).

**Later (not v2):** story/book → screenplay (parser + LLM), then feed the
existing pipeline.

## D. Locked decisions (do not relitigate)

1. Audience first: **power users** (self-run ComfyUI + `llama.cpp`-compatible
   server). One-click/non-technical packaging later.
2. Generation backend: **ComfyUI** HTTP pipeline.
3. Zero-dep core is the **default**, but a directive — not a fanatical rule.
4. Scope order: **Project Manager → ComfyUI → rest**.
5. Project persistence embeds the **raw source inside the bundle**.

## E. Quick verification (run after any change)

```bash
.venv/bin/python -m unittest discover -s tests   # expect 153+ tests OK
.venv/bin/ruff check .                            # expect clean
```
