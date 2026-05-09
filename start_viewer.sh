#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
RESEARCH_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
LAUNCHER="$RESEARCH_ROOT/launch_viewer.py"

case "$(uname -s)" in
    Darwin)
        PYTHON="$SCRIPT_DIR/.venv/bin/python"
        if [[ ! -x "$PYTHON" ]]; then
            echo "ERROR: macOS venv not found at viewer-vidi/.venv/" >&2
            echo "       Create it with: python3 -m venv .venv && .venv/bin/pip install -r requirements.txt" >&2
            exit 1
        fi
        exec "$PYTHON" "$LAUNCHER"
        ;;
    Linux)
        if ! conda run -n viewer_vidi true 2>/dev/null; then
            echo "ERROR: conda env 'viewer_vidi' not found." >&2
            echo "       Create it with: conda env create -f environment.yml" >&2
            exit 1
        fi
        exec conda run -n viewer_vidi python "$LAUNCHER"
        ;;
    *)
        echo "ERROR: unsupported platform: $(uname -s)" >&2
        exit 1
        ;;
esac
