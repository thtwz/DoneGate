# Adaptive Batches Implementation Plan

> **For agentic workers:** Use superpowers:subagent-driven-development. User already approved implementation; do not repeat approval gates.

**Goal:** Deliver automatic single/batch workflow with reusable coverage-bound regression and truthful delivery history.

**Architecture:** A focused BatchService composes the existing service and file stores. Thin CLI/tool adapters expose it; the read-only Web projection combines historical tasks, current health and batch summaries.

**Tech Stack:** Python standard library, existing optional tool SDK, vanilla JS/CSS, pytest.

## Chunk 1: Core batch service
- [ ] Add failing real-repository tests in tests/test_batches.py for mode selection, validation, shared commands, dependency fingerprints, cache freshness, partial failure and input changes.
- [ ] Implement src/donegate_mcp/domain/batches.py and focused storage helpers as needed. Keep existing task/service contracts. Validate before mutation, serialize under workspace lock and store evidence/logs.
- [ ] Add bulk operations, branch activation and supervision support with explicit errors. Focused tests must pass.

## Chunk 2: Entry points
- [ ] Add failing CLI and tool adapter tests in tests/test_batch_adapters.py.
- [ ] Extend cli/main.py with batch subcommands and create-many JSON; extend mcp/server.py and tool_schemas.py with thin batch tools. Compact output retains failures and counts; failed checks exit nonzero.
- [ ] Adapt scripts/pre-commit.sh and pre-push.sh to use active batch checks without per-task regression. Exercise actual hooks.

## Chunk 3: Historical state and dashboard
- [ ] Add regression tests for historical completion surviving code drift while health and present gates flag stale evidence.
- [ ] Modify domain/services.py freshness, lifecycle.py and web/read_model.py to separate ordinary stale evidence from explicit reopen/spec drift.
- [ ] Add Web batch summaries and health rendering to static/app.js/CSS, preserving polling/filter behavior. API reads must not mutate stores.

## Chunk 4: Delivery
- [ ] Update README.md, README.zh-CN.md, CHANGELOG.md and canonical skill/operations with complete runnable batch example and honest limitations.
- [ ] Independent spec/code review; fix material findings. Run final pytest, adapter smoke and browser/API acceptance with temporary project data.
- [ ] Record DoneGate verification/docs/review and completion, commit/push authorized branch/main; reinstall local package and restart only owned dashboard service.
