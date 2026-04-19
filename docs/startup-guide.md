# DoneGate MCP startup guide

## 1. Local development

```bash
cd /Users/mac/workspace/projects/delivery-mcp
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
donegate-mcp --help
```

## 2. Initialize state in a target project

From the target project root:

```bash
donegate-mcp --data-root .delivery-mcp init --project-name my-project
```

## 3. Recommended hook wiring

```bash
cp /Users/mac/workspace/projects/delivery-mcp/scripts/pre-commit.sh .git/hooks/pre-commit
cp /Users/mac/workspace/projects/delivery-mcp/scripts/pre-push.sh .git/hooks/pre-push
chmod +x .git/hooks/pre-commit .git/hooks/pre-push
```

Then export variables in your shell or CI job:

```bash
source /Users/mac/workspace/projects/delivery-mcp/examples/delivery-mcp.env.example
export TASK_ID=TASK-0001
export SPEC_REF=docs/spec.md
```

## 4. MCP integration

Use `examples/hermes-mcp-config.yaml` as a starting point. In practice, prefer packaging DoneGate MCP into the Python environment that Hermes uses, then point `mcp_servers.delivery_mcp.command` to that interpreter.

## 5. Operational note

For local adoption, the CLI is the primary stable interface. The MCP adapter is there for agent orchestration, but hook and CI integration should call the CLI directly.

## 6. Naming note

The public project name is `DoneGate MCP`. The internal Python package path remains `delivery_mcp` for compatibility with the current codebase.
