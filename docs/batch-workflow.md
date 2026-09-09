# Adaptive development and regression

DoneGate keeps each feature traceable while letting related features share a development batch and regression evidence. The host AI chooses a bounded group based on dependencies and risk. DoneGate does not call another model or infer actual test coverage.

## Choose a mode

- `auto` is the default: one task or high risk recommends single mode; multiple normal-risk tasks recommend batch mode. The selected mode and reason are saved.
- `single` preserves independent per-task checks. Use it for isolated fixes or acceptance that needs individual execution.
- `batch` executes a shared declared command once for its covered members. The host can override the recommendation with an explicit rationale.

For a new project, split by module/dependency or an independently testable business flow. Do not defer all validation until hundreds of features are implemented. Use cheap checks during development, regression at batch boundaries, and the appropriate full suite at release boundaries. Every feature still needs explicit acceptance coverage.

## Example

Run these commands in the initialized project. First write `tasks.json` using the project's real paths and tests:

```json
[
  {"title":"Account API", "spec_ref":"docs/accounts.md", "verification_mode":"self-test", "test_commands":["python -m pytest tests/accounts -q"], "owned_paths":["src/accounts", "tests/accounts"]},
  {"title":"Account page", "spec_ref":"docs/accounts.md", "verification_mode":"self-test", "test_commands":["python -m pytest tests/accounts -q"], "owned_paths":["src/accounts", "tests/accounts"]}
]
```

```bash
donegate --json --compact task create-many --file tasks.json
# Substitute the returned task IDs; these IDs are examples.
donegate --json batch create --title "Account workflow" \
  --task-id TASK-0001 --task-id TASK-0002 --mode auto \
  --rationale "Implement the related account flow before a shared regression" \
  --dependencies '{"TASK-0002":["TASK-0001"]}'
# Substitute the returned batch ID.
donegate batch activate BATCH-0001
donegate batch start BATCH-0001
# Implement related changes; run focused checks when useful.
donegate batch submit BATCH-0001
donegate --json --compact batch check BATCH-0001
donegate batch doc-sync BATCH-0001 --result synced --notes "Updated and reviewed account documentation"
donegate batch done BATCH-0001
```

The identical declared regression above runs once in batch mode. Running `batch check` again reuses current successful evidence. `--force` executes checks again, for example when external services changed. `batch show`, `batch list`, `batch active` and `context` expose current grouping and results. Activating a single task exits active batch mode for that branch. Git hooks check an active batch as a unit instead of repeating each member's suite.

## Evidence and impact

Commands listed in each task's acceptance protocol declare which tests cover it. A passing unrelated command cannot verify a task. All required checks and prerequisite conditions must pass; manual tasks need real recorded acceptance. Shared code, test fixtures and configuration must be included in declared scopes; missing scopes conservatively cover the repository. Declare dependency edges rather than relying on task titles to imply them.

Reusable evidence is project-local and bound to scoped inputs, acceptance protocol, dependencies and execution context. Missing logs, changed inputs or failed checks cannot be treated as a cached pass. Successful unaffected checks survive other failures. Each run reports actual executed and reused counts; these are measured check counts, not estimated token savings. Scope or dependency uncertainty calls for broader tests or forced regression. External state is not fully discoverable; force checks when it changes.

This version requires a Git workspace for automatic batch evidence. Existing single-task manual acceptance remains available outside Git. Dashboard health checks validate the recorded execution context; a requested regression compares the live execution environment before reusing checks. Activating a task changes the working context but does not erase its declared batch dependencies: use `task check` to route through its batch, or `batch check` directly.

Historical completion and present verification health are distinct. Ordinary source changes may make evidence stale while preserving an earlier delivery. Explicit task reopening or recorded requirement changes reopen the relevant work. Current completion and Git gates still require fresh passing evidence and synchronized documentation. The dashboard displays batch modes, member progress, latest execution/reuse counts and separate current verification health.
