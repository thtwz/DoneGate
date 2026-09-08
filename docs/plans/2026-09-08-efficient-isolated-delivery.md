# Efficient, isolated DoneGate delivery

## Approved scope

Make normal DoneGate use concise and reliable, isolate concurrent projects, publish a remote feature branch, and update the locally installed skill and MCP. The user also authorized deleting old DoneGate state. Preserve unrelated application configuration and repository files.

## Design

- Resolve each MCP call independently. Explicit absolute repo_root wins over inherited defaults; never remember a previous caller's project. A shared unbound server requires a target. Reject conflicting data roots and project ownership before mutation. CLI derives its data root from an explicit repo root as well.
- Keep task lifecycle rules in the service. Add compact context (project, branch, active task, gate blockers and next action), task activation, and opt-in compact responses across CLI/MCP. Preserve existing full response contracts by default.
- Bind passed verification to a deterministic snapshot of scoped repository inputs, spec and acceptance protocol. Detect changed evidence before done and supervision. Exclude DoneGate state and declared generated artifacts; test changes during self-test. Preserve compatibility for legacy non-Git task data while exposing missing evidence binding in Git repositories.
- Keep advisory review nonblocking. Reuse a completed review for unchanged review inputs, and avoid duplicate requests caused only by timestamps.
- Keep SKILL.md small: precise triggers, one context read, reuse active work, record actual evidence, concise completion. Move CLI examples and exceptional operations into one optional reference. Use returned IDs and configure self-test before invoking it. Document that doc-sync is always a recorded fact, including an explained no-change result.

## Implementation and verification

- [ ] Add two-project, wrong-root, unbound-server and compact-response regression tests, then implement transport/context changes.
- [ ] Add stale-evidence, scope, generated-artifact and unchanged-review tests, then implement domain changes.
- [ ] Rewrite the skill and runnable reference, synchronize plugin packaging/version and release documentation.
- [ ] Run full pytest, installed stdio MCP smoke tests, real CLI lifecycle and two-project isolation checks, and independently review the diff and skill behavior.
- [ ] Record verification/doc facts, commit and push the feature branch; verify remote SHA.
- [ ] Remove confirmed old DoneGate data, install the released local package/skill, update shared MCP configuration and verify a freshly started server.

## Boundaries

Do not merge main or publish a package registry release. Keep the repository's three-component package version scheme. Do not install extra review infrastructure or alter other plugins. New migration checks must report actionable errors rather than silently taking ownership of another project's data.
