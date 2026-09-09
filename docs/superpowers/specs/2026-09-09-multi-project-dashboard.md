# Multi-project delivery dashboard

User approved the design on 2026-09-09 and authorized implementation.

## Outcome

One local Web process serves a portfolio of registered DoneGate workspaces. Developers can compare delivery progress, inspect individual features and their evidence, and trace requirement changes to affected tasks. The Web process is independent of MCP and ships with the Python package, without a frontend build or remote dependencies.

## Scope and behavior

- `donegate-mcp ui` serves loopback HTTP on port 8765 by default. `--port`, `--registry`, `--no-open`, and repeatable `--project` allow explicit configuration. Existing global `--repo-root` registers that workspace. No project initialization as a side effect.
- A per-user registry stores opaque workspace keys, canonical repo/data paths and project identity. Add paths through the UI once; persist across restart. Remove unregisters only. Every read validates current ownership and identity; missing/moved/corrupt projects display isolated errors. Worktrees remain distinct, even when display names or task numbers coincide.
- `/` is portfolio; `/projects/<key>/overview`, `/features`, `/changes` are bookmarkable views. A task detail displays acceptance protocol, verification/doc facts, artifacts/references and event history. Group features by spec reference (no invented module hierarchy).
- Completion rate = tasks whose current derived status is done / total managed tasks. Empty projects show no rate. In-progress is not a guessed percentage. Needs-revalidation is an orthogonal flag and visible in both overview and feature details. Show count denominator, last refresh, loading, empty and error states. Poll every 5 seconds without losing filters, focus or opened details.
- Requirement history combines captured revisions, legacy drift events and declared deviations. Capture content snapshots when a task first references an existing spec and on explicit `spec refresh`; versions increment only when content changes. Changes include time, reason, previous/current hash and affected task IDs. Preserve content chronology including A → B → A. Diff only known adjacent versions; legacy unavailable text is explicitly marked. Viewing pages never creates revisions, changes task facts or runs tests. Unrecorded filesystem edits are not fabricated into recorded changes.
- Browser API accepts only registered opaque project keys for reads. Local-only server validates Host and Origin, requires same-origin JSON for registration mutations, limits bodies, serves only bundled static files, and never provides arbitrary filesystem or command execution endpoints. Render all project text as text, including diffs.
- Per-project reads use existing domain status derivation and evidence freshness checks without persisting task changes. Consistent reads coordinate with the existing workspace write lock. Snapshot history writes share that lock with CLI/MCP operations.
- Registry mutations are atomic and locked across processes. Read projection must not construct stores/services that create directories; tests compare filesystem contents before/after GET, including stale evidence. Historical affected task IDs are captured at revision time, never expanded by later task creation.
- This is local multi-project visibility; no remote aggregation, authentication, scheduling estimates, or task mutation UI.

## API contract

`GET /api/projects` → `{projects: [{key, project_id, project_name, repo_root, data_root, error, summary, updated_at}]}`.
`POST /api/projects` JSON `{repo_root, data_root?}` → `{project: entry}`; `DELETE /api/projects/<key>` unregisters.
`GET /api/projects/<key>` → `{project: entry, summary, tasks, changes, updated_at, warnings}`.
Summary: `{total_tasks, done_tasks, completion_rate, counts_by_status, needs_revalidation, blocked_tasks}`. `completion_rate` is 0–100 or null.
Tasks retain DoneGate task fields, plus `events: [{type,timestamp,actor,payload}]`. Changes: `{id, kind, spec_ref, timestamp, reason, version, previous_version, affected_task_ids, diff, history_available}`. Kinds: `snapshot`, `spec_drift`, `deviation`; diff is a unified diff string or null. Payloads can add useful labels and details.
Each change also supplies `previous_hash` and `current_hash` when known. Errors use JSON `{error: message}`, non-2xx status. GET detail returns 404 for unknown key and 422 for unusable registered project. Portfolio continues after a project error.

## Validation

Automated tests use independent real temporary repositories to verify duplicate task IDs, ownership mismatch, registry restart, removed repos, empty state, evidence-derived progress, requirement drift/revalidation, exact diff, unchanged refresh and legacy history. HTTP integration exercises real sockets, deep links, invalid keys, request guards, bundled assets and registration. Existing suite must remain green. Browser acceptance checks actual add/select/filter/detail/history/remove flows, refresh after CLI update, mobile layout and displayed error states. Wheel includes all assets.
