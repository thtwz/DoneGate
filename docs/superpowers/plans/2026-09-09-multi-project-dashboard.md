# Multi-project dashboard implementation plan

> Execute using superpowers:subagent-driven-development; approval to implement was supplied in the conversation.

**Goal:** Deliver the approved local portfolio, feature completion and requirement change UI.

**Architecture:** A bundled static client and loopback Python HTTP server share DoneGate domain/storage rules with CLI and MCP. A user registry selects isolated workspaces; spec snapshots extend existing refresh operations.

**Tech Stack:** Python standard library, vanilla HTML/CSS/JS, pytest, browser acceptance.

## Chunk 1: History and read API

- [x] Add failing history tests in `tests/test_spec_history.py`: first snapshot, repeat no-op, sequential versions, reverted content, drift task impact and legacy missing baseline.
- [x] Implement `storage/spec_store.py`; integrate capture into `domain/services.py` `_spec_snapshot` and `refresh_spec` without changing lifecycle semantics.
- [x] Add failing tests in `tests/test_web.py` for canonical registry registration, identity changes, isolated duplicate task IDs, missing projects, truthful progress and no mutations on reads.
- [x] Implement `web/registry.py` and `web/read_model.py`, using canonical path+identity keys and existing domain normalization/freshness logic. Return the API contract from the spec.
- [x] Run `.venv/bin/python -m pytest tests/test_spec_history.py tests/test_web.py -q` and resolve failures.

## Chunk 2: Local server and client

- [x] Add HTTP integration tests for project CRUD, invalid inputs/Host/Origin, deep links, bundled assets and unknown paths.
- [x] Implement `web/server.py` and CLI `ui` parser/dispatch; package `web/static/*` through `pyproject.toml`.
- [x] Implement `web/static/index.html`, `app.css`, `app.js`: Chinese developer interface, portfolio cards, sidebar, grouped/filterable feature list, evidence/details, change timeline/diff. Preserve view state across polling and handle network/per-project errors.
- [x] Test browser flows against real temporary repositories and inspect desktop/mobile screenshots. Ensure no synthetic data appears in the product.

## Chunk 3: Delivery

- [x] Update `README.md`, `README.zh-CN.md`, `CHANGELOG.md` with startup, registration, local-only scope and history baseline semantics.
- [x] Review spec compliance, then code quality, and fix actionable issues.
- [x] Build wheel and verify packaged assets.

Final delivery protocol: run the full pytest suite through DoneGate self-test; record browser evidence and doc sync, resolve the final gate, and leave the working preview running for the user. See `2026-09-09-dashboard-acceptance.md` and the task self-test artifacts for evidence.
