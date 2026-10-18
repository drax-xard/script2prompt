# Big Fish (2003) — local test screenplay

This folder is a drop point for the *Big Fish* screenplay (written by **John
August**, based on the novel by Daniel Wallace), used as an
**industry-standard** end-to-end input for the parser → scenes → bible →
chunker → prompt pipeline.

## Why the files are not in this repository

The screenplay is **© 2003 Columbia Pictures** — it is **not** public domain and
carries no redistribution rights. It is therefore **not committed** and is
excluded from release archives. The three source files are listed in the root
`.gitignore` (`samples/Big_Fish/*.pdf`, `*.fdx`, `*.fountain`) so they cannot be
added by accident.

## Getting the files

Obtain the screenplay from the author's official script library on
**johnaugust.com** ("Library"). John August publishes his screenplays there for
educational reading — review his terms before redistributing anything.

Drop whichever formats you have here:

| File | Parser exercised |
| --- | --- |
| `Big-Fish.fountain` | `script2prompt/parsers/fountain.py` |
| `Big-Fish.fdx` | `script2prompt/parsers/fdx.py` |
| `Big-Fish.pdf` | `script2prompt/parsers/pdf.py` (needs the `pdf` extra) |

`.fountain` and `.fdx` cover the structured formats; `.pdf` covers the
lazy-`pypdf` path. Comparing all three for the same script is a useful check
that the parsers agree scene-for-scene.

## Using it

A full feature is far larger than the bundled `samples/one_page.txt`, so run it
straight through the CLI (see `README.md` / `docs/TESTING.md`), e.g.:

```sh
.venv/bin/python -m script2prompt samples/Big_Fish/Big-Fish.fountain -o out/bigfish
.venv/bin/python -m script2prompt samples/Big_Fish/Big-Fish.fdx -o out/bigfish-fdx
```

Expect many chunks, a large character bible, and per-chunk prompts that still
validate clean — a realistic stress test for chunking, budgets, and speaker-ID
assignment.
