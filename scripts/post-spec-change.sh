#!/usr/bin/env bash
set -euo pipefail
: "${SPEC_REF:?SPEC_REF is required}"
ROOT=${DONEGATE_MCP_ROOT:-.donegate-mcp}
REASON=${1:-spec file changed}
PYTHONPATH=${PYTHONPATH:-src} python3 -m donegate_mcp.cli.main --data-root "$ROOT" --json spec refresh --spec-ref "$SPEC_REF" --reason "$REASON"
