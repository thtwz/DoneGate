#!/usr/bin/env bash
set -euo pipefail
: "${TASK_ID:?TASK_ID is required}"
: "${DOC_REF:=docs/plan.md}"
ROOT=${DONEGATE_MCP_ROOT:-.donegate-mcp}
RESULT=${1:-synced}
PYTHONPATH=${PYTHONPATH:-src} python3 -m donegate_mcp.cli.main --data-root "$ROOT" task doc-sync "$TASK_ID" --result "$RESULT" --ref "$DOC_REF"
