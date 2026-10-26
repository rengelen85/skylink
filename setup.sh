#!/usr/bin/env bash
# Init script: makes sure uv is available, then creates .venv with polars + pytest.
# Usage: ./setup.sh            (afterwards: uv run pytest)
set -euo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")"

if ! command -v uv >/dev/null 2>&1; then
    # the installer puts uv in ~/.local/bin (or $XDG_BIN_HOME)
    export PATH="$HOME/.local/bin:$PATH"
fi
if ! command -v uv >/dev/null 2>&1; then
    echo "uv not found - installing (https://docs.astral.sh/uv/)..."
    if command -v curl >/dev/null 2>&1; then
        curl -LsSf https://astral.sh/uv/install.sh | sh
    elif command -v wget >/dev/null 2>&1; then
        wget -qO- https://astral.sh/uv/install.sh | sh
    else
        echo "need curl or wget to install uv" >&2; exit 1
    fi
    export PATH="$HOME/.local/bin:$PATH"
    command -v uv >/dev/null 2>&1 || { echo "uv installed but not on PATH; add ~/.local/bin to PATH" >&2; exit 1; }
fi

uv sync
echo
echo "Ready. Run the validation with:"
echo "    uv run pytest            # fast checks"
echo "    uv run pytest --regen    # also regenerate the dataset and diff (determinism)"
