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
        "max_tokens": 2048,
        "timeout": 120,
        "retries": 2,
        "fix_attempts": 1,
        "context": True,
        "disable_thinking": True,
    },
}


def load(path: str | Path = "config.toml", local_override: str | Path = "config.local.toml") -> dict:
    """Load config.toml with optional local override file and env vars."""
    cfg = {section: dict(values) for section, values in DEFAULTS.items()}
    for candidate in (Path(path), Path(local_override)):
        if candidate.is_file():
            try:
                with candidate.open("rb") as fh:
                    data = tomllib.load(fh)
            except tomllib.TOMLDecodeError as exc:
                raise ValueError(f"invalid TOML in {candidate}: {exc}") from exc
            for section, values in data.items():
                if isinstance(values, dict) and section in cfg:
                    cfg[section].update(values)
                else:
                    cfg[section] = values
    if os.environ.get("OPENAI_BASE_URL"):
        cfg["llm"]["base_url"] = os.environ["OPENAI_BASE_URL"]
    if os.environ.get("S2P_MODEL"):
        cfg["llm"]["model"] = os.environ["S2P_MODEL"]
    if os.environ.get("S2P_TEMPERATURE"):
        cfg["llm"]["temperature"] = _env_number("S2P_TEMPERATURE", float)
    if os.environ.get("S2P_TIMEOUT"):
        cfg["llm"]["timeout"] = _env_number("S2P_TIMEOUT", int)
    return cfg


def _env_number(name: str, cast):
    """Parse an environment override with a friendly error naming the variable."""
    raw = os.environ[name]
    try:
        return cast(raw)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"invalid {name}: {raw!r} (expected a number)") from exc
