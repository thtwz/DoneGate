# Changelog

## 0.4.1 — 2026-09-08

- Use one shared MCP across projects with explicit per-call repository targeting. Conflicting ownership is rejected; initialization no longer resets existing tasks.
- Inspect the current task and delivery blockers in one concise context call. Activate/get tasks through MCP and request compact mutation responses instead of full task payloads.
- Detect code, spec and acceptance changes after verification. Self-tests run in the bound project and reject input changes during execution.
- Reuse current verification in git hooks, including manual evidence, and propagate failed check exit codes.
- Reuse completed advisory reviews when reviewed inputs are unchanged. Advisory findings remain nonblocking.
- Reduce the default skill instructions and move CLI examples into an optional reference. Fix self-test setup, document no-change doc sync, and avoid creating tasks for read-only discussions.
- Align package/plugin/runtime versions and keep shared plugin configuration independent of any one project.

Git snapshots cover scoped tracked and nonignored untracked inputs, spec and required docs. Declared output artifacts and DoneGate state are excluded. Non-Git workflows still require operators to check evidence freshness manually.
