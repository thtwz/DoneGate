#!/usr/bin/env bash
set -euo pipefail
: "${SPEC_REF:?SPEC_REF is required}"
ROOT=${DELIVERY_MCP_ROOT:-.delivery-mcp}
REASON=${1:-spec file changed}
PYTHONPATH=${PYTHONPATH:-src} python3 -m delivery_mcp.cli.main --data-root "$ROOT" --json spec refresh --spec-ref "$SPEC_REF" --reason "$REASON"
