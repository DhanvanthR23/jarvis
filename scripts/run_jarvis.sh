#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

if [ ! -f "/var/log/jarvis/anchor.log" ]; then
    echo "Error: anchor.log not found in /var/log/jarvis." >&2
    echo "Please run scripts/setup_anchor.sh first to initialize the audit anchor." >&2
    exit 1
fi

if [ -f "$PROJECT_ROOT/.venv/bin/python" ]; then
    PYTHON_BIN="$PROJECT_ROOT/.venv/bin/python"
else
    PYTHON_BIN="python3"
fi

export PYTHONPATH="$PROJECT_ROOT:${PYTHONPATH:-}"

exec "$PYTHON_BIN" -m jarvis.cli.main "$@"
