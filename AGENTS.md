# AGENTS.md

## Environment

- Project-local venv only: run everything via `.venv/bin/python` and `.venv/bin/pip`.
  Never bare `pip install`, never `--system`, never `sudo`. `.venv/` is git-ignored.
- Verify: `.venv/bin/python -m unittest discover -s tests`
- Lint: `.venv/bin/ruff check .` (needs the `dev` extra).

## Dependencies

- Core keeps **zero required third-party deps** (stdlib: `dataclasses`, `tomllib`,
  `urllib.request`, `unittest`, `xml.etree`). This is the *default* and a directive
  ("avoid dependency abuse"), **not an absolute hard rule** — see the locked v2
  decision in `IMPROVEMENTS.md`. A `1.0` desktop bundle may add heavier
  **optional** extras (`pywebview`, a managed `llama-server` sidecar, `.s2p` zip
  bundles) as long as core stays dependency-free.
- Optionals are lazy-imported inside functions, never at module top level:
  `pypdf` in `parsers/pdf.py` (`.[pdf]`), `streamlit` in `app/web.py` (`.[web]`).
  Missing-extra errors must name the exact install command.
- `dev` extra (`ruff`) is tooling only (`.venv/bin/ruff check .`) — never imported
  by the package.
- Rejected so far (rationale in `PROJECT_PLAN.md` §3.2): `pydantic`, `pyyaml`,
  `openai` SDK, `pytest`, `pdfplumber`, `fastapi`. Bundled Chromium/CEF is also
  rejected (dependency abuse). Rejected entries are not a blanket ban on *any*
  new optional extra — evaluate each against the directive above.

## Config

- `config.toml` via `core/config.py:load()` (stdlib `tomllib`).
  Precedence: `config.toml` < `config.local.toml` < env
  (`OPENAI_BASE_URL`, `S2P_MODEL`, `S2P_TEMPERATURE`, `S2P_TIMEOUT`).
- `load()` takes explicit paths — tests pass nonexistent paths to check defaults.

## Tests

- Stdlib `unittest`, not pytest: `.venv/bin/python -m unittest discover -s tests`
- `pyproject.toml` has no pytest config; don't add one.

## H3 prompt rules (authoritative sources)

- Prompt shapes live in `H3_Prompting_Docs/` (official Minimax guides) and are
  summarized in `PROJECT_PLAN.md` §2. Read those before touching
  `core/modes.py`, `core/h3_builder.py`, or `core/validator.py`.
- Non-obvious rules agents get wrong: `[Shot 1]` never has a timestamp;
  speaker IDs count *voices* (`S1` = first voice, non-vocal characters get none);
  voice description goes *outside* `<d>`, verbatim words *inside*;
  `overall_soundscape` must never contain dialogue; v1 mode is per-project
  (`chunk.mode_override` is a v2 hook — don't implement it yet).
- Real-prompt layout (`H3_Prompting_Docs/Example_*.txt`, which overrides the
  guides on style): field labels on their own lines, style as standalone opening
  sentence before `[Shot 1]`, dialogue as `Name (S1) says <d>[Lang]words</d>.`
  (no colon, no space after language tag, period outside `</d>`).

## Workflow

- No commits unless asked. `CHANGELOG.md` (Keep a Changelog + SemVer):
  record every behavior/dependency change under `Unreleased`.
- Don't create `*.md` files unprompted; `PROJECT_PLAN.md` is the design doc.
