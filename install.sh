#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$ROOT"

VENV="$ROOT/.venv"
VENV_PY="$VENV/bin/python"

if ! command -v python3 >/dev/null 2>&1; then
    echo "error: python3 not found on PATH" >&2
    exit 1
fi

if ! python3 -c 'import sys; raise SystemExit(0 if sys.version_info >= (3, 11) else 1)'; then
    echo "error: Python >=3.11 required (found: $(python3 --version 2>&1))" >&2
    exit 1
fi

if [ ! -x "$VENV_PY" ]; then
    echo "creating virtualenv at .venv..."
    python3 -m venv "$VENV"
fi

usage() {
    echo "usage: $0 [none|pdf|web|both]" >&2
}

pick_extra() {
    # $1: raw selection; echoes the extras string (may be empty)
    case "$1" in
        0|none|"") echo "" ;;
        1|pdf)     echo "pdf" ;;
        2|web)     echo "web" ;;
        3|both)    echo "pdf,web" ;;
        *) return 1 ;;
    esac
}

if [ "$#" -gt 0 ]; then
    raw="$1"
else
    echo "Which optional extras should be installed?"
    echo "  0) none - core only (no third-party deps)"
    echo "  1) pdf  - PDF input (pypdf)"
    echo "  2) web  - Streamlit web wizard"
    echo "  3) both - pdf + web"
    read -r -p "Choice [0]: " raw || true
    raw="${raw:-0}"
fi

if ! extras="$(pick_extra "$raw")"; then
    echo "error: unrecognised choice '$raw'" >&2
    usage
    exit 1
fi

if [ -z "$extras" ]; then
    spec="."
    echo "installing core only..."
else
    spec=".[$extras]"
    echo "installing extras: $extras..."
fi

"$VENV_PY" -m pip install -e "$spec"

echo
echo "done. versions:"
"$VENV_PY" --version
"$VENV_PY" -c 'from importlib.metadata import version; print("script2prompt", version("script2prompt"))' 2>/dev/null || true
if [ "$extras" = "web" ] || [ "$extras" = "pdf,web" ]; then
    echo "launch the web wizard with: ./run_web.sh"
fi
