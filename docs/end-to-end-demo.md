# DoneGate MCP end-to-end demo

This walkthrough shows the full spec-driven loop:
- create task from spec
- run self-test
- sync docs
- close task
- modify spec
- detect drift
- record deviation
- inspect progress

## Setup

```bash
cd /path/to/DoneGate-MCP
mkdir -p /tmp/delivery-demo/docs /tmp/delivery-demo/reports
printf 'version 1\n' >/tmp/delivery-demo/docs/spec.md
printf 'plan\n' >/tmp/delivery-demo/docs/plan.md
printf 'pytest ok\n' >/tmp/delivery-demo/reports/pytest.txt
donegate-mcp --data-root /tmp/delivery-demo/.donegate-mcp init --project-name demo
```

## Create a task

```bash
donegate-mcp --data-root /tmp/delivery-demo/.donegate-mcp --json task create \
  --title "implement gate" \
  --spec-ref /tmp/delivery-demo/docs/spec.md \
  --verification-mode self-test \
  --test-command "python3 -c 'print(42)'" \
  --required-doc-ref /tmp/delivery-demo/docs/plan.md \
  --required-artifact /tmp/delivery-demo/reports/pytest.txt \
  --plan-node-id phase-1-gate
```

## Drive it to done

```bash
TASK_ID=TASK-0001
donegate-mcp --data-root /tmp/delivery-demo/.donegate-mcp task transition $TASK_ID --to ready
donegate-mcp --data-root /tmp/delivery-demo/.donegate-mcp task start $TASK_ID
donegate-mcp --data-root /tmp/delivery-demo/.donegate-mcp task submit $TASK_ID
donegate-mcp --data-root /tmp/delivery-demo/.donegate-mcp --json task self-test $TASK_ID --workdir /tmp/delivery-demo
donegate-mcp --data-root /tmp/delivery-demo/.donegate-mcp task doc-sync $TASK_ID --result synced --ref /tmp/delivery-demo/docs/plan.md
donegate-mcp --data-root /tmp/delivery-demo/.donegate-mcp --json task done $TASK_ID
```

## Change the spec and detect drift

```bash
printf 'version 2\n' >/tmp/delivery-demo/docs/spec.md
donegate-mcp --data-root /tmp/delivery-demo/.donegate-mcp --json spec refresh --spec-ref /tmp/delivery-demo/docs/spec.md --reason "design updated"
donegate-mcp --data-root /tmp/delivery-demo/.donegate-mcp --json progress
```

Expected result:
- task shows `needs_revalidation=true`
- progress includes the task under `stale_tasks`

## Record a deviation

```bash
donegate-mcp --data-root /tmp/delivery-demo/.donegate-mcp deviation add $TASK_ID \
  --summary "temporary workaround" \
  --details "using compatibility path until final API lands"
donegate-mcp --data-root /tmp/delivery-demo/.donegate-mcp --json deviation list
```

## Inspect state files

```bash
cat /tmp/delivery-demo/.donegate-mcp/plan.json
cat /tmp/delivery-demo/.donegate-mcp/progress.json
cat /tmp/delivery-demo/.donegate-mcp/deviations.jsonl
```
