---
name: donegate
description: Use whenever working in a repository governed by `.donegate-mcp/`, before code changes, before claiming work is done, before commit or push, or when the user mentions DoneGate, delivery gate, verification, doc sync, task state, spec drift, governed delivery, or acceptance evidence.
---

# DoneGate

Use this skill proactively for governed delivery work. If the repository contains `.donegate-mcp/`, treat DoneGate as part of the normal engineering workflow, not as an optional tool the user must explicitly request.

## Architecture Contract

DoneGate integration is deliberately layered:

- Domain/storage is the source of truth. It owns task facts, lifecycle projection, locking, read-model sync, validation, and migration.
- CLI is the mandatory control plane. Hooks, CI, humans, and agents must be able to complete the workflow through `donegate-mcp` without MCP.
- Skill is the host operating protocol. It tells the agent when to create tasks, inspect specs, record verification, record doc sync, reopen work, and refuse conversational completion.
- MCP is an optional structured agent adapter. Use it when available because it is convenient for host tools, but do not treat MCP as required for DoneGate to work.
- Plugin is the host packaging shell. It exposes this skill, starts optional MCP tools, and wires lightweight hooks.
- Hooks are triggers. They may inspect or remind, but they must not become a second lifecycle implementation.

If these layers disagree, trust CLI/domain state and fix the domain model or this skill. Do not patch around the disagreement in a hook script.

## Required Behavior

1. Before editing in a governed repo, inspect onboarding, active task, or supervision.
2. Read the governing spec/doc before making claims about task state.
3. Use DoneGate CLI or MCP tools for lifecycle changes.
4. Treat verification and doc sync as recorded facts, not assistant narration.
5. Check dashboard/supervision before claiming the repo is clean.
6. Before commit or push, verify the active task covers the changed paths and has current evidence.
7. When advisory reviews are pending, perform the host-side review and record normalized findings through DoneGate.

## Tool Preference

Use MCP tools when they are exposed by the host:

- `project_dashboard`
- `task_create`
- `task_list`
- `task_transition`
- `task_record_verification`
- `task_record_doc_sync`
- `task_run_self_test`
- `spec_refresh`
- `review_list`
- `task_review`
- `task_create_from_finding`

Use the CLI when MCP tools are unavailable, stale, or not pointed at the correct repo:

```bash
donegate-mcp --data-root .donegate-mcp --json onboarding --repo-root . --agent codex
donegate-mcp --data-root .donegate-mcp --json supervision --repo-root .
donegate-mcp --data-root .donegate-mcp --json dashboard --include-tasks
```

## Task Storage Model

Raw task JSON does not persist `status`. Persisted lifecycle inputs are:

- `workflow_intent`
- `verification_status`
- `doc_sync_status`
- `blocked_reason`
- `needs_revalidation`
- timestamps and refs such as `done_at`, `verified_at`, `last_verification_ref`

CLI/MCP/read-model responses still return `status` as a compatibility alias for the projected lifecycle phase. Treat `status` as `projected_status`, not source-of-truth state.

If direct file inspection is unavoidable, absence of `status` in `.donegate-mcp/tasks/TASK-xxxx.json` is expected. Never reintroduce a persisted `status` field.

## Normal Flow

1. Inspect onboarding and dashboard:

```bash
donegate-mcp --data-root .donegate-mcp --json onboarding --repo-root . --agent codex
donegate-mcp --data-root .donegate-mcp --json dashboard --include-tasks
```

2. Ensure work is attached to a task:

```bash
donegate-mcp --data-root .donegate-mcp --json task create --title "<work>" --spec-ref "<spec>"
donegate-mcp --data-root .donegate-mcp task activate TASK-0001 --repo-root .
```

3. During work, record real state:

```bash
donegate-mcp --data-root .donegate-mcp task start TASK-0001
donegate-mcp --data-root .donegate-mcp task submit TASK-0001
donegate-mcp --data-root .donegate-mcp --json task self-test TASK-0001 --workdir .
donegate-mcp --data-root .donegate-mcp task doc-sync TASK-0001 --result synced --ref <doc-or-spec>
donegate-mcp --data-root .donegate-mcp task done TASK-0001
```

4. If completed work resumes, reopen it explicitly:

```bash
donegate-mcp --data-root .donegate-mcp --json task reopen TASK-0001
```

## Hook Discipline

Plugin hooks and git hooks may call `supervision`, `onboarding`, or `task self-test`. They must not encode lifecycle projection rules. If a hook needs a stronger policy, add the policy to DoneGate domain/CLI first, then have the hook call that stable interface.

## Completion Standard

Do not report DoneGate-governed work as done unless:

- verification is recorded as passed
- doc sync is recorded as synced when docs are required
- required artifacts exist
- dashboard has no missing verification/doc blockers for the task
- any advisory findings are either recorded as follow-up work or deliberately waived
