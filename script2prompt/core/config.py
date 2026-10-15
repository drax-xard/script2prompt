"""Project configuration loader (stdlib tomllib, no third-party deps)."""
from __future__ import annotations

import os
import tomllib
from pathlib import Path

DEFAULTS = {
    "project": {
        "mode": "T2VA",
        "duration": 8.0,
        "shots_max": 3,
        "style": "Live-action, cinematic",
    },
    "llm": {
        "base_url": "http://localhost:11434/v1",
        "model": "local-model",
        "temperature": 0.3,
    },
}


def load(path: str | Path = "config.toml", local_override: str | Path = "config.local.toml") -> dict:
    """Load config.toml with optional local override file and env vars."""
    cfg = {section: dict(values) for section, values in DEFAULTS.items()}
    for candidate in (Path(path), Path(local_override)):
        if candidate.is_file():
            with candidate.open("rb") as fh:
                data = tomllib.load(fh)
            for section, values in data.items():
                if isinstance(values, dict) and section in cfg:
                    cfg[section].update(values)
                else:
                    cfg[section] = values
    if os.environ.get("OPENAI_BASE_URL"):
        cfg["llm"]["base_url"] = os.environ["OPENAI_BASE_URL"]
    if os.environ.get("S2P_MODEL"):
        cfg["llm"]["model"] = os.environ["S2P_MODEL"]
    return cfg
