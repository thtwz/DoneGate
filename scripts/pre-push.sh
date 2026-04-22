#!/usr/bin/env bash
set -euo pipefail
ROOT=${DONEGATE_MCP_ROOT:-.donegate-mcp}
WORKDIR=${DONEGATE_MCP_WORKDIR:-$(pwd)}
REPO_ROOT=${DONEGATE_MCP_REPO_ROOT:-$WORKDIR}
STAGE=pre_push
export STAGE

if [ -z "${TASK_ID:-}" ]; then
  ACTIVE_JSON=$(PYTHONPATH=${PYTHONPATH:-src} python3 -m donegate_mcp.cli.main --data-root "$ROOT" --json task active --repo-root "$REPO_ROOT" 2>/dev/null || true)
  TASK_ID=$(printf '%s' "$ACTIVE_JSON" | python3 -c 'import json, sys
data = sys.stdin.read().strip()
if not data:
    raise SystemExit(1)
payload = json.loads(data)
task = payload.get("active_task") or {}
task_id = task.get("task_id")
if not task_id:
    raise SystemExit(1)
print(task_id)' 2>/dev/null || true)
fi

: "${TASK_ID:?TASK_ID is required; set TASK_ID or activate a task in DoneGate}"
if git -C "$REPO_ROOT" rev-parse --is-inside-work-tree >/dev/null 2>&1; then
  SUPERVISION_JSON=$(PYTHONPATH=${PYTHONPATH:-src} python3 -m donegate_mcp.cli.main --data-root "$ROOT" --json supervision --repo-root "$REPO_ROOT")
  POLICY=$(printf '%s' "$SUPERVISION_JSON" | python3 -c 'import json, os, sys
payload = json.loads(sys.stdin.read())
supervision = payload.get("supervision") or {}
stage = os.environ["STAGE"]
policy = (supervision.get("policy") or {}).get(stage) or {}
status = supervision.get("status", "unknown")
action = policy.get("action", "allow")
print(f"{action}:{status}")')
  ACTION=${POLICY%%:*}
  STATUS=${POLICY#*:}
  if [ "$ACTION" = "block" ]; then
    printf 'DoneGate %s blocked on %s\n' "$STAGE" "$STATUS" >&2
    exit 1
  fi
  if [ "$ACTION" = "warn" ]; then
    printf 'DoneGate %s warning: %s\n' "$STAGE" "$STATUS" >&2
  fi
fi
PYTHONPATH=${PYTHONPATH:-src} python3 -m donegate_mcp.cli.main --data-root "$ROOT" --json task self-test "$TASK_ID" --workdir "$WORKDIR" >/tmp/donegate-mcp-self-test.json
