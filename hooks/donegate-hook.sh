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
    SUPERVISION_JSON="$("$CLI" --data-root "$ROOT/.donegate-mcp" --json supervision --repo-root "$ROOT" 2>/dev/null || true)"
    if [ -n "$SUPERVISION_JSON" ]; then
      printf '%s' "$SUPERVISION_JSON" | python3 -c 'import json, sys
try:
    payload = json.loads(sys.stdin.read())
except Exception:
    raise SystemExit(0)
supervision = payload.get("supervision") or {}
summary = supervision.get("advisory_summary") or {}
pending = int(summary.get("pending_reviews") or 0)
open_count = int(summary.get("open_advisories") or 0)
if pending or open_count:
    print(f"DoneGate advisory attention: pending_reviews={pending} open_advisories={open_count}", file=sys.stderr)
' || true
    fi
    ;;
esac

exit 0
