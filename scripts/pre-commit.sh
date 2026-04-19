#!/usr/bin/env bash
set -euo pipefail
: "${TASK_ID:?TASK_ID is required}"
ROOT=${DELIVERY_MCP_ROOT:-.delivery-mcp}
WORKDIR=${DELIVERY_MCP_WORKDIR:-$(pwd)}
PYTHONPATH=${PYTHONPATH:-src} python3 -m delivery_mcp.cli.main --data-root "$ROOT" --json task self-test "$TASK_ID" --workdir "$WORKDIR"
