"""Command-line entry point: ``python -m script2prompt SCRIPT [options]``.

Generates the export pack (prompts + manifests) for a screenplay. Uses the
deterministic templates by default; pass ``--llm`` to rewrite via the configured
OpenAI-compatible endpoint (falls back to templates if unreachable). Prints a
per-project budget summary and lint warnings; ``--strict`` exits non-zero on any
warning.
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
    parser.add_argument("--shots", type=int, help="max shots per chunk override (1-3)")
    parser.add_argument("--config", help="config file to load (default: config.toml)")
    parser.add_argument("--llm", action="store_true", help="rewrite prompts via the LLM endpoint")
    parser.add_argument("--clean", action="store_true", help="remove stale pack files before writing")
    parser.add_argument("--strict", action="store_true", help="exit non-zero if any lint warning")
    args = parser.parse_args(argv)

    cfg = config_mod.load(args.config or "config.toml")
    mode = args.mode or cfg["project"]["mode"]
    style = args.style or cfg["project"]["style"]
    duration = args.duration if args.duration is not None else cfg["project"]["duration"]
    shots = args.shots if args.shots is not None else cfg["project"]["shots_max"]

    elements = parse_file(args.script)
    project = pipeline.run(
        elements, mode=mode, duration=duration, shots_max=shots, style=style,
        rewrite=llm.rewrite if args.llm else None,
    )
    written = pipeline.write_pack(project, args.out, clean=args.clean)

    summary = pipeline.budgets(project)
    warnings = pipeline.lint(project)
    print(f"mode={mode} chunks={len(project.results)} -> {args.out}/")
    print(f"  total {summary['total_duration']:.2f}s, {summary['total_chars']} chars "
          f"(budget {summary['char_budget']}/chunk)")
    print("  " + ", ".join(written))
    for warning in warnings:
        print(f"  warning: {warning}")
    return 1 if warnings and args.strict else 0


if __name__ == "__main__":
    raise SystemExit(main())
