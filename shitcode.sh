#!/usr/bin/env bash
# ShitCode Local Client Launcher for Linux
set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

if command -v python3 &>/dev/null; then
    PYTHON_CMD=python3
else
    PYTHON_CMD=python
fi

if ! $PYTHON_CMD -c "import websockets, httpx, bs4" &>/dev/null; then
    echo "[ShitCode] Installing required dependencies..."
    $PYTHON_CMD -m pip install -q -r requirements.txt
fi

exec $PYTHON_CMD shitcode.py "$@"
