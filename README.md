# Script2Prompt

Translate movie scripts (screenplays) into Minimax H3 video prompts. Point it
at a screenplay and it produces a ready-to-use prompt pack: one validated H3
prompt per 5–10s chunk, with a consistent character bible.

**Status: `0.9.0` (pre-1.0).** All core features and all five H3 modes are
implemented, tested, and validated end-to-end. Output format may still change at
a minor bump until 1.0. See [`CHANGELOG.md`](CHANGELOG.md) for history and
[`IMPROVEMENTS.md`](IMPROVEMENTS.md) for the audit/backlog.

## What it does

`parse → scenes → character bible → 5–10s chunks → H3 prompts → validate → export`

- **Parsers:** plain text, Fountain, Final Draft (`.fdx`), PDF (`.pdf`).
- **Scene splitter:** cuts on `INT./EXT.`/`EST.` sluglines, carrying location/time context.
- **Character bible:** stable speaker IDs (`S1`, `S2`, …) in first-vocalization
  order, with descriptions captured from `NAME (traits)` action intros.
- **Chunker:** greedy packing with a speech/action duration estimate, capped at
  10s and 3 shots; long monologues split with `<scenetrans>` markers.
- **Builders + validator:** deterministic templates by default, optional LLM
  rewrite, and a linter for the H3 rules (fields, shots, timestamps, dialogue
  tags, soundscape/music budgets, speaker IDs, 7000-char cap).

### Modes

| Mode | Meaning | References |
| ---- | ------- | ---------- |
| `T2VA` | Text to video + audio | none |
| `I2VA` | Text + first frame | 1 image |
| `FL2VA` | Text + first and last frames | 2 images, single shot |
| `L2VA` | Text + last frame | 1 image |
| `R2V` | Full reference (6-section format) | subject images + voice samples |

## Requirements

- Python `>=3.11` (stdlib `tomllib`).
- **Zero required third-party dependencies.** `pypdf` (`.pdf` input) and
  `streamlit` (web UI) are lazy-imported optional extras.

## Install

Project-local virtualenv only:

```bash
python3 -m venv .venv
.venv/bin/pip install -e .            # core
.venv/bin/pip install -e ".[pdf]"     # optional PDF input
.venv/bin/pip install -e ".[web]"     # optional web wizard
```

## Usage

CLI (deterministic templates by default; `--llm` opt-in):

```bash
.venv/bin/python -m script2prompt samples/one_page.txt -m T2VA -o out
.venv/bin/python -m script2prompt samples/one_page.txt --duration 8 --llm
```

Options: `-m/--mode {T2VA,I2VA,FL2VA,L2VA,R2V}`, `-o/--out DIR`,
`--style TEXT`, `--duration SECONDS`, `--llm`.

Web wizard (requires the `web` extra):

```bash
.venv/bin/streamlit run script2prompt/app/web.py
```

Upload → pick mode/settings → review/edit the bible → generate → download the pack.

### Output pack

Written to the `-o` directory:

- `prompts.md` – all prompts with per-chunk validation warnings
- `manifest.json` – mode, characters, chunks, speakers
- `reference_manifest.json` – reference slots (non-`T2VA` modes only)
- `characters.md` – the character bible
- `chunk_NN.txt` – one file per chunk

## Configuration

Defaults live in [`config.toml`](config.toml), loaded with stdlib `tomllib`.
Precedence: `config.toml` < `config.local.toml` < env vars
(`OPENAI_BASE_URL`, `S2P_MODEL`). The LLM endpoint must be OpenAI-compatible
(no SDK required; defaults target a local server on `http://localhost:11434/v1`).

## Project layout

```
script2prompt/
  parsers/   input formats -> elements (plaintext, fountain, fdx, pdf)
  core/      scenes, characters, chunker, modes, builders, validator, llm, pipeline, config
  app/       web.py (Streamlit wizard)
  __main__.py  CLI entry point
tests/       stdlib unittest suite
samples/     sample screenplays
```

## Tests

```bash
.venv/bin/python -m unittest discover -s tests
```

## Docs

- [`PROJECT_PLAN.md`](PROJECT_PLAN.md) – design, dependency policy, milestones.
- [`H3_Prompting_Docs/`](H3_Prompting_Docs/) – official Minimax H3 prompting guides.
- [`CHANGELOG.md`](CHANGELOG.md) – release history (Keep a Changelog + SemVer).
- [`IMPROVEMENTS.md`](IMPROVEMENTS.md) – code audit, fixes, and backlog.
