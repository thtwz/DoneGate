#!/usr/bin/env bash
set -euo pipefail
: "${TASK_ID:?TASK_ID is required}"
ROOT=${DONEGATE_MCP_ROOT:-.donegate-mcp}
WORKDIR=${DONEGATE_MCP_WORKDIR:-$(pwd)}
PYTHONPATH=${PYTHONPATH:-src} python3 -m donegate_mcp.cli.main --data-root "$ROOT" --json task self-test "$TASK_ID" --workdir "$WORKDIR"
