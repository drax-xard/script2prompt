# AGENTS.md

## Environment

- Project-local venv only: run everything via `.venv/bin/python` and `.venv/bin/pip`.
  Never bare `pip install`, never `--system`, never `sudo`. `.venv/` is git-ignored.
- Verify: `.venv/bin/python -m unittest discover -s tests`

## Dependencies

- Core has **zero required third-party deps** (stdlib: `dataclasses`, `tomllib`,
  `urllib.request`, `unittest`, `xml.etree`). Keep it that way.
- Optionals are lazy-imported inside functions, never at module top level:
  `pypdf` in `parsers/pdf.py` (`.[pdf]`), `streamlit` in `app/web.py` (`.[web]`).
  Missing-extra errors must name the exact install command.
- Rejected (don't reintroduce): `pydantic`, `pyyaml`, `openai` SDK, `pytest`,
  `pdfplumber`, `fastapi`. Rationale in `PROJECT_PLAN.md` §3.2.

## Config

- `config.toml` via `core/config.py:load()` (stdlib `tomllib`).
  Precedence: `config.toml` < `config.local.toml` < `OPENAI_BASE_URL` / `S2P_MODEL` env.
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

## Workflow

- No commits unless asked. `CHANGELOG.md` (Keep a Changelog + SemVer):
  record every behavior/dependency change under `Unreleased`.
- Don't create `*.md` files unprompted; `PROJECT_PLAN.md` is the design doc.
