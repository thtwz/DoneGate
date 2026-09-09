# DoneGate startup guide

For project background and the agent-oriented overview, start with [README.md](../README.md). If you prefer Chinese, use [README.zh-CN.md](../README.zh-CN.md).

## 1. Local development

```bash
cd /path/to/DoneGate
python3 -m venv .venv
. .venv/bin/activate
pip install -e .
```

For optional MCP support:

```bash
pip install "mcp>=1.9.0"
```

After installation, the primary CLI is:

```bash
donegate --help
```

## 2. Bootstrap a target project

From the target project root, prefer a single bootstrap command:

```bash
donegate bootstrap --project-name my-project --repo-root .
```

This will:
- initialize `.donegate-mcp`
- install managed `pre-commit` and `pre-push` hooks into the resolved git hooks directory
- keep unknown existing hooks untouched and report them as skipped
- generate `.donegate-mcp/env.sh`
- generate `.donegate-mcp/onboarding/codex.md`
- generate `.donegate-mcp/onboarding/hermes-mcp.yaml`

The hook installation path is worktree-safe, so linked git worktrees do not need a separate setup flow.

## 3. Manual initialization path

If you want to initialize state without installing hooks, use:

```bash
donegate init --project-name my-project
```

## 4. Recommended manual hook wiring

```bash
cp /path/to/DoneGate/scripts/pre-commit.sh .git/hooks/pre-commit
cp /path/to/DoneGate/scripts/pre-push.sh .git/hooks/pre-push
chmod +x .git/hooks/pre-commit .git/hooks/pre-push
```

Then export variables in your shell or CI job:

```bash
source /path/to/DoneGate/examples/donegate-mcp.env.example
export TASK_ID=TASK-0001
export SPEC_REF=docs/spec.md
```

For local repository work, you can also set the repo-local active task instead of exporting `TASK_ID` every time:

```bash
donegate task activate TASK-0001 --repo-root .
donegate --json task active --repo-root .
```

The managed `pre-commit` and `pre-push` hooks will use the active task automatically when `TASK_ID` is absent.

When `--repo-root .` points at a git repository, DoneGate records the active task against the current branch, so different branches can carry different active task bindings.

You can also ask DoneGate to inspect whether the repository currently has work that is not tied to an active task:

```bash
donegate --json supervision --repo-root .
```

If you already know which parts of the repository a task should own, declare them up front:

```bash
donegate --json task create \
  --title "branch context follow-up" \
  --spec-ref docs/spec.md \
  --owned-path src/donegate_mcp \
  --owned-path tests
```

With task scopes in place, supervision can tell you whether the active task fully covers the current diff or whether it has drifted into `task_mismatch`.

The richer supervision statuses are:
- `needs_task`
- `task_mismatch`
- `needs_revalidation`
- `stale_verification`
- `stale_docs`
- `tracked`

Managed hook behavior now uses those statuses before self-test:
- `pre-commit` blocks on `needs_task`, `task_mismatch`, and `needs_revalidation`
- `pre-commit` warns but continues on `stale_verification` and `stale_docs`
- `pre-push` blocks on any status stronger than `tracked`

## 5. Onboarding command

After bootstrap, ask DoneGate for repo-local agent guidance:

```bash
donegate --json onboarding --repo-root . --agent codex
donegate --json onboarding --repo-root . --agent hermes
```

The response includes the current branch, any branch-bound active task, the generated onboarding file paths, and the next recommended command if work still needs to be attached to a task.

## 6. Advisory review

Advisory review helps agents catch outcome gaps that can pass verification while still missing the real user need. It is advisory in v0.4: findings do not block `done`, but they stay visible and can be converted into follow-up tasks.

DoneGate creates review requests when a task first enters submitted-for-verification and again before completion. Re-running the same lifecycle command reuses the existing pending request instead of adding duplicates:

```bash
donegate task submit TASK-0001
donegate --json review list --task-id TASK-0001 --include-findings
```

Record a finding from a human, Codex skill, or other host reviewer:

```bash
donegate --json task review TASK-0001 \
  --checkpoint manual \
  --provider manual \
  --summary "The implementation passes the literal gate but leaves a user-value gap." \
  --recommendation proceed_with_followups \
  --finding-json '{"dimension":"outcome_gap","severity":"medium","title":"Missing fast path","details":"Frequent users still need too many steps.","recommended_action":"Add a shortcut flow.","suggested_task_title":"Add fast path","suggested_task_summary":"Reduce repeated-user steps."}'
```

Create tracked follow-up work from the finding:

```bash
donegate --json task create-from-finding FINDING-1234abcd
donegate --json review disposition FINDING-1234abcd --to accepted
```

Once a finding is converted into a follow-up task, it is counted separately from open advisories so the dashboard shows unresolved advisory work distinctly from tracked follow-up work.

The dashboard includes `tasks_with_pending_reviews` for requested reviews that still need host-side attention. The Codex plugin `Stop` hook also prints a concise advisory reminder when pending reviews or open advisory findings remain; it does not perform review logic itself.

Review run payloads include provider audit fields. `provider_id` remains the compatibility field for the provider that completed the review, while `requested_provider_id` and `completed_provider_id` preserve request and completion provenance separately.

MCP clients should use the matching tools: `task_review`, `review_list`, `review_disposition`, and `task_create_from_finding`.

## 7. MCP integration

### Hermes native MCP

Use `examples/hermes-mcp-config.yaml` as a starting point.
If Hermes runs DoneGate from the delivery checkout, the typical setup is:

```yaml
mcp_servers:
  donegate:
    command: "/Users/mac/workspace/projects/DoneGate/.venv/bin/donegate"
    args: ["serve"]
    env:
      DONEGATE_MCP_DATA_ROOT: "/absolute/path/to/.donegate-mcp"
    timeout: 120
    connect_timeout: 30
```

After changing the code, update the environment Hermes uses by reinstalling the editable package in that venv:

```bash
cd /Users/mac/workspace/projects/DoneGate
/Users/mac/workspace/projects/DoneGate/.venv/bin/pip install -e '.[mcp,test]'
```

If you use Hermes skills, load the `donegate` skill before governed work so the operator flow stays aligned with DoneGate facts instead of chat narration.

### Trae / plugin-style MCP clients

For Trae-style plugin configs, point the plugin at the same `donegate serve` entrypoint and data root:

```json
{
  "mcpServers": {
    "donegate": {
      "command": "/Users/mac/workspace/projects/DoneGate/.venv/bin/donegate",
      "args": ["serve"],
      "env": {
        "DONEGATE_MCP_DATA_ROOT": "/absolute/path/to/.donegate-mcp"
      }
    }
  }
}
```

## 8. Codex plugin integration

Install in the environment that launches the server:

```bash
python3 -m pip install -e ".[mcp]"
```

The canonical skill lives in `skills/donegate/`, including its optional references.
Copy the complete directory when installing a standalone skill. The plugin manifest
uses `scripts/donegate-serve-plugin.sh`; `.mcp.json` offers the same configuration.
Keep only one active registration per host to avoid duplicated skill/MCP context.

For a shared Codex MCP, use an absolute installed interpreter or server entrypoint,
with no fixed data directory:

```toml
[mcp_servers.donegate]
command = "/absolute/DoneGate/.venv/bin/donegate"
args = ["serve"]
```

Every tool call must supply the target worktree's absolute `repo_root`. A shared
server never adopts a previous caller's repository or its installation directory.
Explicit repo targeting wins over inherited defaults; explicit conflicting roots
and stores owned by another repo are rejected before state changes. A task ID is
only meaningful with its project. Separate worktrees use separate state directories.

Use `project_context` for active task, branch, blockers and next action. Fetch
`task_get` only when full acceptance details are needed. `task_activate` binds an
existing task; mutation tools accept `compact: true`. The CLI supports equivalent
operations and global targeting:

```bash
donegate --repo-root /absolute/project --json context
donegate --repo-root /absolute/project --json task show TASK-0001
donegate --repo-root /absolute/project --json --compact task activate TASK-0001
```

In a deliberately project-bound CLI/server, `.donegate-mcp/env.sh` may still be
used locally. Do not export its project-specific variables globally into a shared
host. If ownership is wrong, correct the target or reset the specific old store
with user authorization. `init` on the same store is idempotent and does not erase
tasks; it cannot take ownership of another project.

Git evidence is bound to scoped working-tree content, spec and acceptance inputs.
Changing them invalidates verification before delivery; staging or committing the
same content does not. Self-test uses the project directory, stores logs outside
the response, and fails if inputs change during execution. Declare generated
outputs as artifacts or ignore build products in Git to avoid unnecessary rechecks.
Non-Git repositories still need explicit manual freshness checks.

Reload/reconnect the host's MCP after updating the runtime or configuration. Check
a fresh stdio server's version and tool list; an already running process retains
its loaded code. Newly loaded skills use the updated canonical directory.

## 9. Operational note

For local adoption, the CLI is the primary stable interface. The MCP adapter is there for agent orchestration, but hook and CI integration should call the CLI directly.

## 10. Naming note

The public product, package, and primary command are DoneGate / `donegate`. Historical Python imports remain compatible; use `donegate serve` only when an agent integration is needed.
