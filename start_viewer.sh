#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
LAUNCHER="$SCRIPT_DIR/run.py"

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
        CONDA_EXE="${CONDA_EXE:-}"
        if [[ -z "$CONDA_EXE" ]]; then
            for candidate in \
                "$HOME/miniconda3/bin/conda" \
                "$HOME/anaconda3/bin/conda" \
                "/opt/conda/bin/conda" \
                "/usr/local/bin/conda"; do
                if [[ -x "$candidate" ]]; then
                    CONDA_EXE="$candidate"
                    break
                fi
            done
        fi
        if [[ -z "$CONDA_EXE" ]]; then
            echo "ERROR: conda not found. Set CONDA_EXE or add conda to PATH." >&2
            exit 1
        fi
        if ! "$CONDA_EXE" run -n viewer_vidi true 2>/dev/null; then
            echo "ERROR: conda env 'viewer_vidi' not found." >&2
            echo "       Create it: $CONDA_EXE create -n viewer_vidi python=3.10 -y && pip install -r requirements.txt" >&2
            exit 1
        fi
        exec "$CONDA_EXE" run -n viewer_vidi python "$LAUNCHER"
        ;;
    *)
        echo "ERROR: unsupported platform: $(uname -s)" >&2
        exit 1
        ;;
esac
