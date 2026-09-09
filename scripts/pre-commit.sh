#!/usr/bin/env bash
set -euo pipefail
ROOT=${DONEGATE_MCP_ROOT:-.donegate-mcp}
WORKDIR=${DONEGATE_MCP_WORKDIR:-$(pwd)}
REPO_ROOT=${DONEGATE_MCP_REPO_ROOT:-$WORKDIR}
STAGE=pre_commit
export STAGE

if [ -z "${TASK_ID:-}" ] && [ -z "${BATCH_ID:-}" ]; then
  BATCH_JSON=$(PYTHONPATH=${PYTHONPATH:-src} python3 -m donegate_mcp.cli.main --repo-root "$REPO_ROOT" --data-root "$ROOT" --json batch active 2>/dev/null || true)
  BATCH_ID=$(printf '%s' "$BATCH_JSON" | python3 -c 'import json,sys
try:
    print((json.load(sys.stdin).get("batch") or {}).get("batch_id", ""))
except (ValueError, TypeError):
    pass' 2>/dev/null || true)
fi

if [ -z "${TASK_ID:-}" ] && [ -z "${BATCH_ID:-}" ]; then
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

if [ -z "${TASK_ID:-}" ] && [ -z "${BATCH_ID:-}" ]; then
  printf 'DoneGate requires an active task or batch\n' >&2
  exit 1
fi
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
if [ -n "${BATCH_ID:-}" ]; then
  PYTHONPATH=${PYTHONPATH:-src} python3 -m donegate_mcp.cli.main --repo-root "$REPO_ROOT" --data-root "$ROOT" --json --compact batch check "$BATCH_ID"
else
  PYTHONPATH=${PYTHONPATH:-src} python3 -m donegate_mcp.cli.main --repo-root "$REPO_ROOT" --data-root "$ROOT" --json task check "$TASK_ID"
fi
