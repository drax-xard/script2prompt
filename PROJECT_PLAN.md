# Script2Prompt — PROJECT_PLAN.md

## 1. Goal

Build a tool that translates generic movie scripts / screenplays into viable, short (5–10s) prompts for the **Minimax H3** video model, preserving the original script's tone and scene context.

Core requirements:
- Accept **plain-text and standard screenplay formats**: `.txt`, `.fountain`, `.fdx`, `.pdf`.
- Split scenes first by **scene heading** (`INT./EXT.`) to preserve context, then further into logical **chunks of up to 10 seconds**.
- **Up to 3 shots per prompt**, following the standard Minimax H3 prompt structure/tags.
- **Characters defined early**; basic description kept consistent, updated only when necessary for scene continuity.
- **Preserve the original script's tone**.
- Support **different H3 modes per project needs** (T2VA, I2VA, FL2VA, L2VA, R2V full-reference), presented as options during parsing. **v1: mode is per-project** (one mode for the whole run); per-scene/per-chunk granularity is a v2 extension.

Agreed stack / approach:
- **Python + web UI** (core library UI-agnostic; Streamlit or FastAPI+Jinja for v1 frontend).
- **Hybrid parser + custom LLM** (deterministic structure extraction + LLM rewrite via **local model over OpenAI-compatible API**; rule-based template fallback when LLM is unreachable).

Official references (local copies, authoritative for prompt shapes):
- `H3_Prompting_Docs/H3 Prompt Writing Guide (Text and Keyframe).md` → T2VA / I2VA / FL2VA / L2VA.
- `H3_Prompting_Docs/H3 Prompt Writing Guide (Reference).md` → R2V full-reference mode.

---

## 2. Minimax H3 prompt structures (from official guides)

### 2.1 Base modes (T2VA / I2VA / FL2VA / L2VA) — 3 fields + optional instruction line

```
[field label on its own line, body follows — per Example_*_Prompt.txt]
integrated_multimodal_description:
Live-action, cinematic.
[Shot 1] ...

overall_soundscape:
...

non_diegetic_music:
N/A
```

Layout note: the guides show labels inline (`field: [Shot 1]...`), but the real
example prompts put each label on its own line with a standalone style sentence
opening the body. Match the examples. Dialogue form is
`Name (S1) says <d>[Lang]words</d>.` (no colon, no space after the language tag,
terminal period outside `</d>`).

| Mode | Use | Instruction line (first line, then one blank line) | Body shape |
|---|---|---|---|
| T2VA | No images; invent from text | *None* — start directly with the three fields | Complete timeline from text; may add consistent scene/character/sound detail |
| I2VA | First frame decided; animate forward | `For the target video, at 0.00 seconds into the target video, <Picture 1> (from [Shot 1]) is fully referenced.` | Anchor Picture 1 (style/subjects/composition in Shot 1) → action onset → development → result; preserve identity/clothing/layout |
| FL2VA | Known start + end; bridge them | `How the reference pictures align with the target video — Picture 1 (from Shot 1) aligns with the 0.00-second mark of the target video; Picture 2 (from Shot N) aligns with the S.SS-second mark of the target video.` | Motion path between frames, not two static descriptions; **favor single shot**; final `[Shot N]` must reach Picture 2 |
| L2VA | Must land on known end frame | `How the reference pictures align with the target video — <Picture 1> (from [Shot N]) aligns with the S.SS-second mark of the target video.` | Plausible preceding state → action/transition path → convergence → last-frame landing |

`N` = actual final shot index; `S.SS` = effective duration with exactly two decimals.

### 2.2 Full-reference mode (R2V) — 6 sections in order

1. `subject_definitions:` — one line per tracked item (`<Subject N>` person/object/style/action, `<Picture N>` frame/keyframe/storyboard anchor, `<Video N>` edit/continuation/structure source, `<Audio N>` copy/reference track). Images used only for identity/style are cited *inside* the `<Subject N>` line, not as standalone entries.
2. `summary:` — one paragraph with `[task-type]` prefix (`keyframe completion`, `reference generation`, `video editing`, `video continuation`, `audio reuse`, `audio reference`, joined with ` + `).
3. `retention_analysis:` — one line per label. Visual markers: `fully_preserved / partially_preserved / attribute_transfer / weak_reference`. Audio markers: `fully_copy / partially_copy / reference / weak_reference`.
4. `detailed_description:` — style in 1–2 sentences *before* `[Shot 1]`; then shot-by-shot playback order (350–500 words typical for generation); reference labels inserted at first appearance and where roles apply.
5. `overall_soundscape:` — ambience + physical sounds.
6. `non_diegetic_music:` — audience-only score.

### 2.3 Shared rules (all modes)

- `[Shot 1]` has **no timestamp**. Later shots: `[Shot N] At MM:SS.mmm, the camera cuts to...` (cut verbs: `cuts to / transitions to / changes to / switches to`; dissolve/fade/wipe only if requested). Cut times strictly increasing, inside duration. Cut only for new subject/space/state/viewpoint/time; otherwise move the camera.
- Camera motion = natural sentence: **motion type** (`Zoom In/Out, Push In/Pull Out, Pan Left/Right, Truck Left/Right, Tilt Up/Down, Pedestal Up/Down, Arc Shot, Tracking Shot, Static Shot, Shake Slightly/Strongly, POV, Roll Clockwise/Counterclockwise`) + optional **amplitude** (`with small/large amplitude`) + optional **speed** (`at slow/fast speed`); omit when medium/normal.
- Speakers: stable IDs `(S1)`, `(S2)`, joint `(S1,S2)`; first voice = `(S1)`; non-vocal characters get no ID. Identifying phrase + ID + action + delivery stay **outside** `<d>`; only ` [Language] verbatim words` inside. Voiceover uses exact phrase `says in an off-screen voiceover` + `lips remain closed` statement. Cross-cut dialogue uses `<scenetrans>` at both joins + continuity note; truncated speech uses `<cutoff>`. In R2V, speaking subjects are `<Subject N> (Sx)`.
- On-screen text in English `"double quotes"`, verbatim, untranslated. Dialogue only in `<d>`.
- `overall_soundscape`: 1–4 sentences, ambience + action + non-verbal human sounds; never dialogue; `N/A` only for explicit full silence. `non_diegetic_music`: 1–3 sentences, instrumentation/tempo/dynamics, no mood words; `N/A` if none.
- English body; original language preserved only inside `<d>` and `"quoted signs"`.
- No negative prompts (single-conditioning sampler) — phrase bans as positives.
- Duration 5–15s; tool target **5–10s/chunk** (default 8s). Dialogue budget ~2.5–3 words/s → 10s ≈ 25–30 spoken words. Prompt char budget ~7000.

---

## 3. Architecture

```
Inputs (.txt / .fountain / .fdx / .pdf)
 → Normalizer → Screenplay Parser (elements)
   → Scene splitter (INT./EXT. headings + context carry-over)
     → Character tracker (bible: name → description + speaker Sx)
       → Chunker (≤10s, ≤3 shots, dialogue budget, FL2VA single-shot preference)
         → Reference-manifest proposer (non-T2VA modes)
           → Prompt builder: LLM rewrite (primary) / template fallback (offline)
             → Per-mode validator/linter → Outputs (web UI + files)
```

Design principle: **deterministic parsing guarantees structure** (headings, speakers, verbatim lines, timestamps); **LLM supplies cinematic prose** (camera choice, soundscape inference, tone match). Tool remains usable offline via fallback templates.

### 3.1 Proposed project structure

```
script2prompt/
  parsers/
    base.py        # Element model: heading/action/character/dialogue/parenthetical/transition
    plaintext.py   # heuristics: ALL-CAPS cues, INT./EXT. regex, blank-line blocks
    fountain.py    # Fountain spec subset
    fdx.py         # Final Draft XML via xml.etree
    pdf.py         # pypdf extraction → plaintext parser (optional pdf extra)
  core/
    scenes.py      # split by heading; slugline context prepended to each chunk; SCENE 0 for cold opens
    characters.py  # first-vocalization order → S1..; description captured once, reused verbatim
    chunker.py     # seconds estimate; greedy pack to target; monologue split with <scenetrans>; MM:SS.mmm stamps
    modes.py       # mode enum, instruction-line renderers, section schemas per mode
    h3_builder.py  # base 3-field builder (T2VA/I2VA/FL2VA/L2VA) + r2v_builder (6 sections)
    ref_manifest.py# proposed Subject/Picture/Video/Audio slots per chunk
    llm.py         # stdlib urllib client for OpenAI-compatible endpoint (base_url/model from env + config.toml); 5 mode system prompts
    fallback.py    # rule-based filler when LLM unreachable
    validator.py   # per-mode checks: field order, shot count, timestamps, <d> balance, N/A rules, budgets, label consistency
    config.py      # stdlib tomllib loader for config.toml (+ config.local.toml + env overrides)
  app/
    web.py         # wizard UI (Streamlit, optional web extra); core stays UI-agnostic
  tests/ + samples/
  config.toml    # project defaults + llm endpoint (stdlib tomllib)
```

### 3.2 Dependency use policy

1. **Project-local venv only.** All Python runs/installs use `.venv/bin/...`
   (`python3 -m venv .venv` once; then `.venv/bin/python`, `.venv/bin/pip`).
   Never bare `pip install`, never `--system`, never `sudo`. `.venv/` is git-ignored.
2. **Stdlib first; zero required third-party deps.** Core (Milestones 1–4) installs
   nothing: models are `@dataclass`, validation is hand-written, tests use `unittest`,
   config uses `tomllib`, FDX uses `xml.etree`, LLM calls use `urllib.request`.
   This is the **default and a directive** ("avoid dependency abuse"), not an
   absolute prohibition — see item 5.
3. **A new external package is allowed only when** (a) the problem is not reasonably
   solvable with stdlib (e.g. PDF text extraction), or (b) the user explicitly
   chooses a heavy tool for iteration speed (Streamlit for the web wizard).
4. **Approved optionals (lazy-imported, never required by core):**
   - `pdf = ["pypdf>=4.0"]` — `parsers/pdf.py` only; missing-extra error tells the
     exact install command. `pdfplumber` rejected (pypdf suffices).
   - `web = ["streamlit>=1.30"]` — `app/web.py:main()` only; `fastapi/uvicorn`
     rejected (Streamlit chosen for v1).
   - `dev = ["ruff>=0.6"]` — lint tooling only; never imported by the package and
     not required to run or test it.
5. **Rejected so far:** `pydantic` (dataclasses suffice), `pyyaml` (moved to
   TOML), `openai` SDK (urllib POST suffices), `pytest` (unittest suffices),
   `pdfplumber` (pypdf suffices), `fastapi/uvicorn` (Streamlit chosen for v1),
   bundled Chromium/CEF (dependency abuse). These are per-case decisions, not a
   blanket ban: the zero-dep core is a **directive, not a fanatical rule** (locked
   v2 decision in `IMPROVEMENTS.md` § *Decisions*). A `1.0` desktop bundle may add
   heavier **optional** extras — `pywebview` (`desktop`), a managed `llama-server`
   sidecar, `.s2p` zip bundles — provided the core stays dependency-free and the
   extras remain lazy-imported.
6. **Record every dependency decision** here and in `CHANGELOG.md` under `Unreleased`.

---

## 4. Parsing & chunking logic

1. **Scene split:** case-insensitive `^(INT|EXT)\.` (incl. `INT./EXT.`, `EST.`); slugline (location + time) stored as `context` and prepended to every chunk from that scene.
2. **Element parse:** character cue = short fully-uppercase line preceding a dialogue block; parentheticals kept as delivery hints; transitions (`CUT TO:`) treated as shot-break hints only.
3. **Character bible:** `S#` assigned in order of first *vocalization* (H3 rule). Physical/voice description captured once from action intro or parenthetical; reused verbatim; LLM may update only on explicit script-stated change (costume/age/setting) for continuity.
4. **Chunking (per scene):** `seconds ≈ action_words/2.5*0.4 + dialogue_words/2.75 + 1.0s per shot break`; greedy-pack beats to target (default 8s, cap 10s), max 3 shots. Monologues >30 words split at sentence boundaries with `<scenetrans>` + carry-over sentence. Cut stamps spread evenly (e.g. 10s/3 shots → `00:03.300`, `00:06.600`). **FL2VA: prefer 1 shot/chunk.**
5. **LLM prompts:** system prompt embeds the mode's field spec + camera vocab + dialogue-tag spec + "preserve tone, never paraphrase dialogue, English body"; user message sends scene context + bible entries + chunk beats + duration + style. Temperature ~0.3. Response parsed strictly; `validator.py` rejects/repairs malformed output.
6. **Reference manifest (v1, no image upload):** tool emits placeholders + user checklist fulfilled externally —
   I2VA: one `Picture 1` slot/chunk (tool writes first-frame description); FL2VA/L2VA: `Picture 1 (+2)` slots bound to `S.SS`; R2V: Subject/Picture/Video/Audio table proposed from script (characters, locations, voice-timbre vs. reuse roles).

---

## 5. Web UI flow (wizard; mode per-project for v1)

1. **Upload + auto-parse** — file in → elements → scenes preview.
2. **Project settings** — mode radio cards (T2VA default; each card: use case, references needed, example instruction line) + duration/style/LLM endpoint fields. Locks `project.mode` for all chunks (`chunk.mode_override` reserved for v2).
3. **Review** — scene list → chunks with mode badge (locked) + character bible panel (`S#` + description, editable).
4. **Reference manifest** — mode-dependent slots/checklist (hidden for T2VA).
5. **Generate → Export** — mode-aware build → validation → export pack:
   - `prompts.md` (copy-paste ready) and/or per-chunk `.txt`,
   - `manifest.json` (timings, shots, speakers, mode),
   - `reference_manifest.json` (non-T2VA modes),
   - `characters.md` (bible).

---

## 6. Milestones (status: milestones 1–8 done, 149 tests green)

1. ✅ Offline core: parsers (txt/fountain) + scenes + bible + chunker + T2VA builder/validator + tests. *Done (`35c17c7`).*
2. ✅ Mode layer: `modes.py` + I2VA/FL2VA/L2VA instruction lines + body shapes + per-mode validation. *Done (`72fedda`).*
3. ✅ R2V layer: manifest proposer + 6-section builder + retention markers. *Done (`a239b02`, fixes in `03fbf0a`).*
4. ✅ LLM wiring: 5 mode system prompts via local OpenAI-compatible endpoint + fallback templates. *Done: `core/prompts.py` + `core/llm.py:messages/rewrite` + `h3_builder.build(rewrite=...)`.*
5. ✅ Remaining parsers: FDX + PDF. *Done: `parsers/fdx.py` (`xml.etree`), `parsers/pdf.py` (lazy `pypdf`), `parsers/__init__.py:parse_file` dispatch.*
6. ✅ Web wizard + one sample end-to-end per mode (1-page script → prompts + manifests). *Done: `core/pipeline.py` + `app/web.py` (Streamlit) + `__main__.py` CLI + `samples/one_page.txt`; all 5 modes validate clean.*
7. ✅ Polish: budget meters, linter warnings, config, docs. *Done: `pipeline.budgets` + `pipeline.lint`, CLI `--shots/--config/--strict` + budget/lint output, web budget meters + lint panel, duration/shots clamping, README.*
8. ✅ Output quality + LLM robustness (0.10.0): shared `core/render.py`, long-action splitting, tiny-chunk merge, name casing, environment naming, hardened `llm.chat` (`LLMError`, retries, timeouts), GPL-3.0 license, `ruff` dev extra.
9. ✅ Second deep audit (0.11.0): `B16`–`B25` fixes — BOM handling, R2V empty-subject synthesis, voiceover parentheticals, phantom joint names, `title()` designators, Fountain dialogue state, friendly env errors, T2VA reference manifest, empty style, `.spmd` docs.

v2 hooks (no work now): `chunk.mode_override`, image upload/preview, storyboard multi-panel sheets, ComfyUI/API direct submit.

---

## 7. Open defaults (resolved unless noted)

- ✅ Default chunk duration **8s**, style **`Live-action, cinematic`** unless script states otherwise (in `config.toml`).
- ✅ Local endpoint via `OPENAI_BASE_URL` / `S2P_MODEL` env, mirrored in `config.toml` (implemented in `core/config.py:load`).
- ✅ Export set: `prompts.md` + `manifest.json` (+ `reference_manifest.json`, `characters.md`) sufficient for v1? *Resolved — kept as the v1 pack; per-chunk `.txt` added for convenience (Milestone 6).*
