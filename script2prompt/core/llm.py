"""LLM client over stdlib urllib (local OpenAI-compatible endpoint)."""
from __future__ import annotations

import json
import urllib.request

from .config import load


def chat(messages: list[dict], base_url: str | None = None, model: str | None = None,
         temperature: float | None = None, timeout: int = 120) -> str:
    """POST /chat/completions and return the assistant content (no SDK needed)."""
    cfg = load()
    base = (base_url or cfg["llm"]["base_url"]).rstrip("/")
    payload = {
        "model": model or cfg["llm"]["model"],
        "messages": messages,
        "temperature": cfg["llm"]["temperature"] if temperature is None else temperature,
    }
    req = urllib.request.Request(
        f"{base}/chat/completions",
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        body = json.loads(resp.read().decode("utf-8"))
    return body["choices"][0]["message"]["content"]


def rewrite(chunk: dict, mode: str = "T2VA") -> str:
    """Rewrite a chunk into H3 fields via LLM. TODO: per-mode prompts (Milestone 4)."""
    raise NotImplementedError
