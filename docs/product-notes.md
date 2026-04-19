# Product Notes

## Brand

Project name: `DoneGate MCP`

Public-facing docs should use DoneGate MCP consistently. The internal Python module path can remain `delivery_mcp` for compatibility until a later migration.

## Core framing

Position v0.1 as a lightweight quality gate for AI-assisted software delivery.

This project is not a project manager, not a CI platform, and not a general workflow engine. It is the narrow layer that answers one question reliably: can this task honestly be called done?

## Keep

- Hard gate: a task cannot become done without verification pass and doc sync.
- Local-first file state that teams can inspect and optionally commit.
- Hook-friendly CLI as the primary operational surface.
- MCP support as an orchestration layer, not the primary value proposition.
- Strong tests around lifecycle and gate enforcement.
- Spec drift and revalidation as first-class workflow concepts.

## Cut for v0.1

- Full PM system behavior.
- Fancy dashboards or hosted web UI.
- Broad automation beyond explicit tools and hook entrypoints.
- Deep CI-provider-specific integrations.
- Team management, auth, permissions, and approval workflows.

## Positioning statement

`DoneGate MCP prevents AI-assisted tasks from being marked done before verification passes, docs are synced, and changed specs are revalidated.`

## Open-source pitch

DoneGate MCP is for teams that already have code generation and automation, but do not yet have a trustworthy definition of done.

## Tagline options

- `Not done until it passes the gate.`
- `A delivery gate for AI-assisted software work.`
- `Make done mean verified.`
