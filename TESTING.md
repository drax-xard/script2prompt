# Testing Script2Prompt

A step-by-step guide to install, set up, and exercise the tool. Everything runs
from the project root (`script2prompt/`, the folder containing `pyproject.toml`).
Use the project-local virtualenv for every command.

## 0. Prerequisites

- Python **3.11 or newer** (`python3 --version`).
- No required third-party packages. `pypdf` (PDF input) and `streamlit` (web UI)
  are optional extras you install only if you want them.

## 1. Enter the project and create a virtualenv

```bash
cd /home/drax/Documents/Script2Prompt
python3 -m venv .venv
```

(If `.venv/` already exists, skip the `venv` command — never recreate it while
work is in progress.)

## 2. Install the package

```bash
.venv/bin/pip install -e .
```

Optional extras (only if you need them):

```bash
.venv/bin/pip install -e ".[pdf]"   # PDF input via pypdf
.venv/bin/pip install -e ".[web]"   # Streamlit web wizard
.venv/bin/pip install -e ".[dev]"   # ruff linter (development only)
```

## 3. Confirm the install with the test suite (smoke test)

```bash
.venv/bin/python -m unittest discover -s tests
```

Expected: `Ran 153 tests ... OK`. If this fails, stop here — the environment is
not set up correctly and the rest of the guide will not be meaningful.

Optional lint check (needs the `dev` extra):

```bash
.venv/bin/ruff check .
```

## 4. First CLI run (T2VA, the default mode)

```bash
.venv/bin/python -m script2prompt samples/one_page.txt -o out
```

Expected output (counts may differ slightly):

```
mode=T2VA chunks=3 -> out/
  total 19.42s, 1990 chars (budget 7000/chunk)
  prompts.md, manifest.json, characters.md, chunk_01.txt, chunk_02.txt, chunk_03.txt
```

## 5. Inspect the export pack

The `-o out` directory now contains:

```bash
ls out
```

- `prompts.md` – every H3 prompt (copy-paste ready) with any warnings.
- `manifest.json` – mode, characters, chunks, speakers, per-chunk durations.
- `characters.md` – the character bible (`S1`, `S2`, … + descriptions).
- `chunk_NN.txt` – one prompt per file.
- `reference_manifest.json` – reference slots, only for non-`T2VA` modes.

Open a prompt:

```bash
.venv/bin/python -c "print(open('out/chunk_01.txt').read())"
```

Check it has the expected shape: `integrated_multimodal_description:` /
`overall_soundscape:` / `non_diegetic_music:` fields, a style sentence, and
dialogue in `Name (S1) says <d>[English]…</d>.` form.

## 6. Exercise every mode

Run the same sample through all five modes:

```bash
for m in T2VA I2VA FL2VA L2VA R2V; do
  .venv/bin/python -m script2prompt samples/one_page.txt -m $m -o out_$m
done
```

What to look for:

- `T2VA`: no instruction line above `integrated_multimodal_description:`.
- `I2VA`/`L2VA`: an instruction line referencing `<Picture 1>`, one picture slot.
- `FL2VA`: an instruction line, two picture slots (`<Picture 1>`, `<Picture 2>`),
  and **single-shot** chunks.
- `R2V`: a 6-section format (`subject_definitions:`, `summary:`,
  `retention_analysis:`, `detailed_description:`, `overall_soundscape:`,
  `non_diegetic_music:`) plus `out_R2V/reference_manifest.json`.

## 7. CLI options reference

```bash
.venv/bin/python -m script2prompt --help
```

| Option | Meaning |
| ------ | ------- |
| `script` | path to a `.txt` / `.fountain` / `.fdx` / `.pdf` screenplay |
| `-m`, `--mode` | `T2VA`, `I2VA`, `FL2VA`, `L2VA`, or `R2V` (default: from config) |
| `-o`, `--out` | output directory (default: `out`) |
| `--style` | visual style override (default: `Live-action, cinematic`) |
| `--duration` | target chunk seconds (clamped to 5–10) |
| `--shots` | max shots per chunk (clamped to 1–3) |
| `--config` | alternate config file (default: `config.toml`) |
| `--llm` | rewrite prompts via the configured OpenAI-compatible endpoint |
| `--clean` | remove stale pack files before writing the export |
| `--strict` | exit non-zero if there is any lint warning |

Examples:

```bash
# shorter chunks, single-shot
.venv/bin/python -m script2prompt samples/one_page.txt --duration 5 --shots 1

# custom style
.venv/bin/python -m script2prompt samples/one_page.txt --style "Noir, high contrast, 35mm"

# fail the run if the validator/lint reports anything
.venv/bin/python -m script2prompt samples/one_page.txt --strict; echo "exit=$?"
```

`--strict` returns `0` on the sample and `1` on a script that produces warnings
(e.g. one with no speaking characters).

## 8. Try your own screenplay

Point the tool at any file:

```bash
.venv/bin/python -m script2prompt /path/to/your_script.txt -o out_mine
```

Supported inputs:

- `.txt` / `.text` – plain-text screenplay heuristics.
- `.fountain` / `.spmd` – Fountain subset (`.Heading`, `@Character`, `> Transition`).
- `.fdx` – Final Draft XML.
- `.pdf` – extract text, then parse (requires `.[pdf]`).

Malformed/binary input (e.g. a `.docx`) is rejected with a clear "unsupported
binary file" error rather than producing garbage.

## 9. Configuration

Settings are read from `config.toml` (stdlib `tomllib`). Edit it, or override
without touching the file:

```bash
# config.toml
[project]
mode = "T2VA"                # T2VA | I2VA | FL2VA | L2VA | R2V
duration = 8.0               # target seconds per chunk (cap 10.0)
shots_max = 3
style = "Live-action, cinematic"

[llm]
base_url = "http://localhost:11434/v1"
model = "local-model"
temperature = 0.3
max_tokens = 2048
timeout = 120
retries = 2
```

Precedence: `config.toml` < `config.local.toml` < environment variables
(`OPENAI_BASE_URL`, `S2P_MODEL`, `S2P_TEMPERATURE`, `S2P_TIMEOUT`). To test an
alternate config:

```bash
cp config.toml /tmp/test.toml
.venv/bin/python -m script2prompt samples/one_page.txt --config /tmp/test.toml -o out_cfg
```

## 10. Optional: LLM rewrite

With an OpenAI-compatible endpoint running (the default target is a local server
on `http://localhost:11434/v1`, e.g. Ollama):

```bash
OPENAI_BASE_URL=http://localhost:11434/v1 S2P_MODEL=your-model \
  .venv/bin/python -m script2prompt samples/one_page.txt --llm -o out_llm
```

If the endpoint is unreachable or returns nothing, the tool silently falls back
to the deterministic templates, so runs never hard-fail offline.

## 11. Optional: web wizard

Install the `web` extra, then launch Streamlit:

```bash
.venv/bin/pip install -e ".[web]"
.venv/bin/streamlit run script2prompt/app/web.py
```

In the browser: upload a screenplay → choose the mode and settings → review/edit
the character bible → **Generate prompts**. You get per-chunk budget meters and a
lint panel, a preview of each prompt and the reference manifest, and download
buttons for the export pack (plus "Write pack to ./out").

## 12. Troubleshooting

- `Web UI needs the 'web' extra: .venv/bin/pip install .[web]` — install the web
  extra (step 11).
- `PDF support needs the 'pdf' extra: .venv/bin/pip install .[pdf]` — install the
  pdf extra (step 2).
- `invalid TOML in …` — fix the syntax in the offending config file.
- `unsupported binary file …` — the input is not a supported text/FDX/PDF screenplay.
- `warning: chunk N: …` / `--strict` returns `1` — the prompt tripped a validator
  rule (e.g. over the 7000-char budget, bad timestamps). Inspect that chunk's
  entry in `prompts.md`.
- `no characters detected in the screenplay` — no character cues or
  `NAME (traits)` intros were found; check the input formatting.

## 13. Quick one-shot smoke test

```bash
python3 -m venv .venv && \
.venv/bin/pip install -e . && \
.venv/bin/python -m unittest discover -s tests && \
.venv/bin/python -m script2prompt samples/one_page.txt -o out && \
echo "OK: see out/prompts.md"
```
