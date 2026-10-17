#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$ROOT"

VENV_PY="$ROOT/.venv/bin/python"
INSTALL_CMD='.venv/bin/pip install -e ".[web]"'

fail() {
    echo "error: $1" >&2
    echo "       run: $INSTALL_CMD" >&2
    exit 1
}

if [ ! -x "$VENV_PY" ]; then
    fail "no virtualenv found at .venv (expected $VENV_PY)"
fi

if ! "$VENV_PY" -c 'import sys' >/dev/null 2>&1; then
    fail "the .venv python is present but not runnable"
fi

if ! "$VENV_PY" -c 'import streamlit' >/dev/null 2>&1; then
    fail "the web extra is not installed (streamlit is missing)"
fi

if ! "$VENV_PY" -c 'import script2prompt' >/dev/null 2>&1; then
    fail "script2prompt is not installed into the venv"
fi

echo "venv OK - launching web interface..."
exec "$VENV_PY" -m streamlit run "$ROOT/script2prompt/app/web.py" "$@"
