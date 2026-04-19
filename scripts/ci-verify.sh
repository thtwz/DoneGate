#!/usr/bin/env bash
set -euo pipefail
: "${TASK_ID:?TASK_ID is required}"
: "${VERIFY_REF:=reports/ci.log}"
ROOT=${DELIVERY_MCP_ROOT:-.delivery-mcp}
RESULT=${1:-passed}
PYTHONPATH=${PYTHONPATH:-src} python3 -m delivery_mcp.cli.main --data-root "$ROOT" task verify "$TASK_ID" --result "$RESULT" --ref "$VERIFY_REF"
