#!/usr/bin/env bash
set -euo pipefail
# Compatibility entrypoint for existing installations.
exec "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/donegate-serve-plugin.sh" "$@"
