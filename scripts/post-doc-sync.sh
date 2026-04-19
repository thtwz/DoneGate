#!/usr/bin/env bash
set -euo pipefail
: "${TASK_ID:?TASK_ID is required}"
: "${DOC_REF:=docs/plan.md}"
ROOT=${DELIVERY_MCP_ROOT:-.delivery-mcp}
RESULT=${1:-synced}
PYTHONPATH=${PYTHONPATH:-src} python3 -m delivery_mcp.cli.main --data-root "$ROOT" task doc-sync "$TASK_ID" --result "$RESULT" --ref "$DOC_REF"
