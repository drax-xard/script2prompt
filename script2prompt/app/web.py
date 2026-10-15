"""Web wizard: upload -> mode picker -> review/manifest -> generate/export.

Streamlit is an optional ``web`` extra, imported lazily so the core works
without it. Run with ``.venv/bin/pip install .[web]`` then ``.venv/bin/streamlit run ...``.
"""
from __future__ import annotations


def main() -> None:
    """Streamlit entry point. TODO: Milestone 6."""
    try:
        import streamlit  # noqa: F401
    except ImportError as exc:
        raise ImportError(
            "Web UI needs the 'web' extra: .venv/bin/pip install .[web]"
        ) from exc
    raise NotImplementedError


if __name__ == "__main__":
    main()
