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

configure_telemetry_optout() {
    # Add [browser] gatherUsageStats = false to ~/.streamlit/config.toml,
    # preserving any existing content/comments.
    local cfg="$HOME/.streamlit/config.toml"
    python3 - "$cfg" <<'PY'
import re
import sys
from pathlib import Path

path = Path(sys.argv[1]).expanduser()
text = path.read_text(encoding="utf-8") if path.is_file() else ""
active_false = re.compile(r"^[ \t]*gatherUsageStats[ \t]*=[ \t]*false[ \t]*(?:#.*)?$", re.M)
active_true = re.compile(r"^([ \t]*gatherUsageStats[ \t]*=[ \t]*)true[ \t]*(#.*)?$", re.M)

if active_false.search(text):
    print(f"telemetry opt-out already present in {path}")
    raise SystemExit(0)
if active_true.search(text):
    path.write_text(active_true.sub(r"\1false\2", text), encoding="utf-8")
    print(f"updated existing setting in {path} (gatherUsageStats = false)")
    raise SystemExit(0)

lines = text.splitlines()
out: list[str] = []
inserted = False
for line in lines:
    out.append(line)
    if not inserted and line.strip() == "[browser]":
        out.append("gatherUsageStats = false")
        inserted = True
if not inserted:
    if out and out[-1].strip():
        out.append("")
    out += ["[browser]", "gatherUsageStats = false"]

path.parent.mkdir(parents=True, exist_ok=True)
path.write_text("\n".join(out).rstrip("\n") + "\n", encoding="utf-8")
print(f"wrote telemetry opt-out to {path}")
PY
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

installed_web=false
case ",$extras," in
    *,web,*) installed_web=true ;;
esac

if [ "$installed_web" = true ]; then
    echo
    echo "note: Streamlit collects anonymous usage statistics by default and"
    echo "      shows a telemetry notice on the first run. To opt out, add:"
    echo
    echo "          [browser]"
    echo "          gatherUsageStats = false"
    echo
    echo "      to $HOME/.streamlit/config.toml"
    if [ -t 0 ]; then
        read -r -p "Add this opt-out to ~/.streamlit/config.toml now? [y/N]: " optout || true
        case "${optout:-}" in
            y|Y|yes|YES) configure_telemetry_optout ;;
            *) echo "skipped; you can add it manually later." ;;
        esac
    else
        echo "(non-interactive run: skipping; add the setting manually if desired.)"
    fi
    echo
    echo "launch the web wizard with: ./run_web.sh"
fi
