# next-steps.md

Handoff / starting point for the next work session. This is a working notes file,
not a design doc — the v2 design lives in [`IMPROVEMENTS.md`](IMPROVEMENTS.md)
§ *Post-v1 roadmap (v2)*. Keep this file short-lived: delete entries as they land.

## Status snapshot (verified)

- Version **`0.11.1`** (`pyproject.toml`), pre-1.0.
- Tests: **153 green** — `.venv/bin/python -m unittest discover -s tests`.
- Lint: **clean** — `.venv/bin/ruff check .`.
- venv Python: **3.14.4**; `requires-python = ">=3.11"`.
- Working tree has **uncommitted changes**: the Section A loose ends below
  (code + tests + docs) plus the earlier v2 roadmap consolidation. **No commits
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
- No commits unless asked.

---

## A. Loose ends (small cleanups — do before new features) — ✅ DONE

All landed this session (see `CHANGELOG.md` `[Unreleased]`):

- [x] **Doc test-count drift.** Updated to the actual count in `PROJECT_PLAN.md`
      and `TESTING.md`.
- [x] **Stale error message.** `core/fallback.py` now says `build()` handles
      T2VA/I2VA/FL2VA/L2VA and R2V is built by `core.r2v.py`.
- [x] **Dependency-stance docs reconciled** with the locked v2 directive stance
      (`AGENTS.md`, `PROJECT_PLAN.md` §3.2).
- [x] **Package metadata.** `[project.scripts]`, URLs, readme, keywords,
      classifiers (3.11–3.14) in `pyproject.toml`; `script2prompt` console entry
      point works.
- [x] **CI.** `.github/workflows/ci.yml`: unittest on 3.11–3.14, zero-dep import
      check, optional-extras job.
- [x] **`write_pack` clean/overwrite** (`clean=True`, CLI `--clean`) + tests.
- [x] **B14 — compound speaker IDs (`S1,S2`)** implemented with tests.
- [x] **`plaintext` inline-heading nuance** fixed (dialogue-state context).
- [ ] **Secrets discipline (note, not code yet).** If remote OpenAI-compatible
      endpoints are ever supported, keys come from **env only** — never persisted
      in project files. Today only `base_url` exists; keep it that way.

## B. Prerequisites blocking v2 (do before Project Manager work)

These are load-bearing the moment state is persisted (see `IMPROVEMENTS.md`
§ *Prerequisites*):

- [x] **`schema_version`** (`pipeline.SCHEMA_VERSION`) on `manifest.json` /
      `reference_manifest.json`, with `migrate_artifact`/`load_artifact`
      forward-compatible loading. The future project file reuses the same helper.
- [ ] **`core/h3_spec.py` — single source of truth for H3 rules** (camera vocab,
      cut verbs, language tags, section labels, retention markers, budgets:
      5–10s, ≤3 shots, 7000-char cap). Removes the prose/constant drift risk
      between `core/prompts.py` and `core/validator.py`; Settings will display it
      read-only and gate overrides.
- [ ] **Stable chunk IDs** — `"{scene_index}:{first_element_index}-{last_element_index}"`
      so manual edits survive re-parse; a source-hash change marks stale chunks
      rather than discarding work.
- [ ] **Testable state layer.** Move bible-editing and pack assembly out of
      `app/web.py` into `core/` (and cache the parsed file across Streamlit
      reruns) so `web.py` stops being untestable without Streamlit installed
      (`IMPROVEMENTS.md`).

## C. Then the v2 roadmap (locked scope order)

Full detail in `IMPROVEMENTS.md` § *Post-v1 roadmap (v2)*:

1. **Project Manager** — persisted, chunk-addressable `.s2p` bundles (raw source
   embedded), per-chunk lifecycle, layered bibles (character/location/prop/
   continuity/palette), strategies/presets, cross-project library.
2. **ComfyUI integration** — stdlib `urllib` client, `_meta.title` workflow
   placeholder convention, reference-slot substitution, draft vs. production
   workflow tiers, provenance + iteration loop.
3. **Settings/Options page** — layered precedence (defaults < global < project <
   session), validation/ranges, "test connection", read-only `h3_spec`.
4. **Desktop bundle** at `1.0` — `pywebview` optional `desktop` extra (not
   Chromium); optional stdlib-`http.server` rewrite to drop Streamlit.
5. **Built-in LLM** — managed `llama-server` sidecar (reuses `core/llm.py`
   unchanged); download weights on demand, never bundle.

**Later (not v2):** story/book → screenplay (parser + LLM), then feed the
existing pipeline.

## D. Locked decisions (do not relitigate)

1. Audience first: **power users** (self-run ComfyUI + `llama.cpp`-compatible
   server). One-click/non-technical packaging later.
2. Generation backend: **ComfyUI** HTTP pipeline.
3. Zero-dep core is the **default**, but a directive — not a fanatical rule. A
   `1.0` desktop bundle may ship heavier optionals.
4. Scope order: **Project Manager → ComfyUI → rest**.
5. Project persistence embeds the **raw source inside the bundle**.

## E. Quick verification (run after any change)

```bash
.venv/bin/python -m unittest discover -s tests   # expect 153+ tests OK
.venv/bin/ruff check .                            # expect clean
```
