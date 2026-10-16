"""Command-line entry point: ``python -m script2prompt SCRIPT [options]``.

Generates the export pack (prompts + manifests) for a screenplay. Uses the
deterministic templates by default; pass ``--llm`` to rewrite via the configured
OpenAI-compatible endpoint (falls back to templates if unreachable).
"""
from __future__ import annotations

import argparse

from .core import config as config_mod
from .core import llm, pipeline
from .core.modes import MODES
from .parsers import parse_file


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="script2prompt",
        description="Translate a screenplay into Minimax H3 video prompts.",
    )
    parser.add_argument("script", help="path to a .txt/.fountain/.fdx/.pdf screenplay")
    parser.add_argument("-m", "--mode", choices=MODES, help="H3 mode (default: config)")
    parser.add_argument("-o", "--out", default="out", help="output directory (default: out)")
    parser.add_argument("--style", help="visual style override")
    parser.add_argument("--duration", type=float, help="target chunk seconds override")
    parser.add_argument("--llm", action="store_true", help="rewrite prompts via the LLM endpoint")
    args = parser.parse_args(argv)

    cfg = config_mod.load()
    mode = args.mode or cfg["project"]["mode"]
    style = args.style or cfg["project"]["style"]
    duration = args.duration or cfg["project"]["duration"]

    elements = parse_file(args.script)
    project = pipeline.run(
        elements, mode=mode, duration=duration, style=style,
        rewrite=llm.rewrite if args.llm else None,
    )
    written = pipeline.write_pack(project, args.out)

    warned = [res.index for res in project.results if res.issues]
    print(f"mode={mode} chunks={len(project.results)} -> {args.out}/")
    print("  " + ", ".join(written))
    if warned:
        print(f"  validation issues in chunk(s): {warned}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
