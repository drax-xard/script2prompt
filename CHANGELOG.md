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

### Changed
- Dependency policy: project-local `.venv/` only (git-ignored); zero required
  third-party deps for core (stdlib `dataclasses`, `tomllib`, `urllib`, `unittest`,
  `xml.etree`). Optionals are lazy-imported: `pdf` (`pypdf`, used by `parsers/pdf.py`
  only) and `web` (`streamlit`, used by `app/web.py` only). Dropped `pydantic`,
  `pyyaml`, `openai` SDK, `pytest`, `pdfplumber`, `fastapi/uvicorn`.
  See `PROJECT_PLAN.md` §3.2.
- Config format `config.yaml` → `config.toml` (stdlib `tomllib`).
  `PROJECT_PLAN.md` documents the dependency use policy (§3.2).

## [0.1.0] - TBD

_Target: first usable offline core. Nothing released yet._

### Planned
- Plain-text and Fountain parsers, scene splitter, character bible, chunker (<=10s, <=3 shots).
- T2VA prompt builder with template fallback and validator.
- Tests plus sample end-to-end (1-page script -> prompts).

[Unreleased]: https://github.com/YOUR-USER/Script2Prompt/compare/v0.1.0...HEAD
[0.1.0]: https://github.com/YOUR-USER/Script2Prompt/releases/tag/v0.1.0
