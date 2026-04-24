#!/usr/bin/env bash
set -euo pipefail

EVENT="${1:-session-start}"
PLUGIN_ROOT="${CODEX_PLUGIN_ROOT:-$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)}"
CLI="${DONEGATE_MCP_CLI:-$PLUGIN_ROOT/scripts/donegate-mcp-cli-plugin.sh}"
WORKDIR="${DONEGATE_MCP_WORKDIR:-$(pwd)}"

git_root() {
  git -C "$WORKDIR" rev-parse --show-toplevel 2>/dev/null || true
}

ROOT="$(git_root)"
if [ -z "$ROOT" ] || [ ! -d "$ROOT/.donegate-mcp" ]; then
  exit 0
fi

case "$EVENT" in
  session-start)
    "$CLI" --data-root "$ROOT/.donegate-mcp" --json onboarding --repo-root "$ROOT" --agent codex >/dev/null 2>&1 || true
    ;;
  stop)
    "$CLI" --data-root "$ROOT/.donegate-mcp" --json supervision --repo-root "$ROOT" >/dev/null 2>&1 || true
    ;;
esac

exit 0
