---
name: donegate
description: Govern implementation and delivery in repositories initialized with .donegate-mcp, or handle explicit DoneGate requests. Use before governed edits, completion, commit, or push.
---

# DoneGate

Keep delivery facts in DoneGate; use the user's existing authorization. Discussion and read-only reviews do not create tasks or require delivery gates.

## Work with one project and task

- Resolve the current Git worktree root. Pass its absolute `repo_root` on **every MCP call**; task IDs are local to a project. Never reuse another project's active task, inherited data root, or a previous caller's context. A root/ownership mismatch needs correction, not a new task in the wrong store.
- On entering governed work or switching repo/branch, call `project_context` once. It returns the active task, blockers and next action. Reuse that task if its scope fits; fetch `task_get` only for missing acceptance details. Activate a suitable existing task with `task_activate`; create one only when needed, using the returned ID.
- Read relevant spec sections once. Declare the actual changed paths and acceptance method. Configure `test_commands` before self-test; manual acceptance records real observed evidence. Reopen completed work before further changes.

## Record and finish

- Prefer MCP with `compact: true` where supported. Use CLI for an unavailable operation; read [operations](references/operations.md) only when command syntax or recovery is needed.
- Start, implement, submit, then run configured self-test or record actual verification. After changes to code, spec or acceptance inputs, reverify. A remembered pass is insufficient.
- Record doc sync even when no doc edit is needed: inspect the impact and record `synced` with a short reason. Required docs/artifacts must exist. Never invent a passed result to satisfy the gate.
- Review substantial work for user-outcome gaps and record useful findings. Advisory findings are nonblocking; accepted follow-ups may become tasks. Reuse an unchanged completed review; do not repeat reviews for timestamps alone or require users to waive every advisory.
- Call `done` and inspect its result before claiming completion. Before commit/push, refresh `project_context` and honor its policy and scope blockers. Query the full dashboard only for a requested project overview or unresolved diagnosis.

Keep ordinary operation quiet. Reuse known context until inputs change; fetch fresh gate state at delivery boundaries. Report the result, verification evidence and actionable blockers briefly. CLI/domain owns lifecycle policy; skills and hooks must not reimplement it or edit raw state JSON.
