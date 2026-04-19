#!/usr/bin/env bash
set -euo pipefail
: "${TASK_ID:?TASK_ID is required}"
: "${VERIFY_REF:=reports/ci.log}"
ROOT=${DONEGATE_MCP_ROOT:-.donegate-mcp}
RESULT=${1:-passed}
PYTHONPATH=${PYTHONPATH:-src} python3 -m donegate_mcp.cli.main --data-root "$ROOT" task verify "$TASK_ID" --result "$RESULT" --ref "$VERIFY_REF"
