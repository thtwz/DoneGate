# DoneGate operations (0.4.1)

## Targeting and discovery

MCP: pass an absolute `repo_root` on every call. `project_context` is the normal entry; `task_get(task_id)` retrieves full acceptance details. `task_list(limit=10)` is for finding a reusable task when context has none, not a routine companion to context. A shared MCP has no default project. Explicit `data_root` is for intentionally separate stores; mismatched project ownership is an error.

CLI: run in the target worktree, or use global `--repo-root /absolute/repo`. `--json --compact` returns concise machine-readable responses. With older servers, fall back **per operation** to the CLI rather than repeatedly searching for missing tools. If the CLI is not on PATH, use the installation's `scripts/donegate-cli-plugin.sh` with the same arguments.

```bash
donegate --repo-root /absolute/repo --json context
donegate --repo-root /absolute/repo --json task show TASK-0001
```

Initialize only when the user requests adopting DoneGate. Run `bootstrap --project-name <name> --repo-root <repo>` for hooks/onboarding, or `init` for state alone. Do not bootstrap merely to answer a question.

## Self-test delivery

From a target repository that already has its spec and test suite (substitute the project's actual paths and command):

```bash
donegate --json --compact task create --title "Implement the requested change" \
  --spec-ref docs/spec.md --owned-path src --owned-path tests --owned-path docs \
  --verification-mode self-test --test-command 'python3 -m pytest -q' \
  --required-doc-ref docs/spec.md
# Use task.task_id from the result for TASK_ID below.
donegate --json --compact task activate "$TASK_ID"
donegate --json --compact task start "$TASK_ID"
# Implement and update relevant docs, then:
donegate --json --compact task submit "$TASK_ID"
donegate --json --compact task self-test "$TASK_ID"
donegate --json --compact task doc-sync "$TASK_ID" --result synced --ref docs/spec.md
donegate --json --compact task done "$TASK_ID"
```

Self-test runs in the bound project, stores logs under its data directory, and records verification automatically. Inspect `ok`, `exit_code`, and `verification_status`; read logs only for failure diagnosis. Do not run the suite again merely to produce a second recording. Git hooks use `task check` to reuse current evidence or run a missing configured check; failed checks exit nonzero. Changed scoped Git inputs invalidate passed evidence; staging/committing identical content does not. Ignored build products and declared output artifacts are excluded. Non-Git work needs explicit manual freshness checks.

## Manual acceptance, changes and reviews

When no automated check is appropriate, create the task with `--verification-mode manual`, perform the actual acceptance, then record it:

```bash
donegate --json --compact task verify "$TASK_ID" --result passed --ref /path/to/evidence --notes 'Observed the requested outcome'
donegate --json --compact task doc-sync "$TASK_ID" --result synced --notes 'Reviewed documentation impact; no changes required'
```

Use `--result failed` for a failed check. Keep the same task when retrying. For resumed completed work use `task reopen`; for changed specs use `spec refresh --spec-ref <path>` and revalidate affected work. Do not edit persisted lifecycle fields.

For substantial work, inspect `review list --task-id "$TASK_ID" --status requested` only when advisory context requires it. Record the relevant checkpoint with `task review` / `task_review`; zero findings is valid. Findings do not block done. Create follow-up tasks only for useful accepted work, using `task create-from-finding`; `review disposition` records accepted/waived/resolved decisions when warranted. Avoid polling unchanged requests.

## Ownership mismatch

Stop operations on that target and inspect the requested repo/data paths. Do not automatically reset, reinitialize, or delete another project's data. Correct the binding, or perform a user-authorized reset of the specific old store. Keep shared MCP configuration unbound; do not export one project's DONEGATE_MCP_ROOT globally.
