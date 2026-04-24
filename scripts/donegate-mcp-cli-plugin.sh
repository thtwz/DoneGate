#!/usr/bin/env bash
set -euo pipefail

PLUGIN_ROOT="${CODEX_PLUGIN_ROOT:-$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)}"

if [ -x "$PLUGIN_ROOT/.venv/bin/python" ]; then
  export PYTHONPATH="$PLUGIN_ROOT/src${PYTHONPATH:+:$PYTHONPATH}"
  exec "$PLUGIN_ROOT/.venv/bin/python" -m donegate_mcp.cli.main "$@"
fi

if command -v donegate-mcp >/dev/null 2>&1; then
  exec donegate-mcp "$@"
fi

export PYTHONPATH="$PLUGIN_ROOT/src${PYTHONPATH:+:$PYTHONPATH}"
exec python3 -m donegate_mcp.cli.main "$@"
