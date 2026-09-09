#!/usr/bin/env bash
set -euo pipefail
PLUGIN_ROOT="${CODEX_PLUGIN_ROOT:-$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)}"
exec "$PLUGIN_ROOT/scripts/donegate-cli-plugin.sh" serve "$@"
