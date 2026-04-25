from __future__ import annotations

import json
import os
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_codex_plugin_manifest_exposes_skill_mcp_and_hooks() -> None:
    manifest = json.loads((ROOT / ".codex-plugin" / "plugin.json").read_text(encoding="utf-8"))

    assert manifest["name"] == "donegate"
    assert manifest["skills"] == "./skills/"
    assert manifest["hooks"] == "./hooks.json"
    assert manifest["mcpServers"]["donegate_mcp"]["command"] == "${CODEX_PLUGIN_ROOT}/scripts/donegate-mcp-serve-plugin.sh"


def test_plugin_hooks_are_thin_triggers() -> None:
    hooks = json.loads((ROOT / "hooks.json").read_text(encoding="utf-8"))
    hook_script = (ROOT / "hooks" / "donegate-hook.sh").read_text(encoding="utf-8")
    commands = [
        hook["command"]
        for event_hooks in hooks["hooks"].values()
        for matcher in event_hooks
        for hook in matcher["hooks"]
    ]

    assert commands
    assert all("hooks/donegate-hook.sh" in command for command in commands)
    assert "task_transition" not in hook_script
    assert "DoneGate advisory attention" in hook_script


def test_plugin_scripts_are_executable() -> None:
    for path in [
        ROOT / "hooks" / "donegate-hook.sh",
        ROOT / "scripts" / "donegate-mcp-cli-plugin.sh",
        ROOT / "scripts" / "donegate-mcp-serve-plugin.sh",
    ]:
        assert os.access(path, os.X_OK), f"{path} must be executable"


def test_canonical_skill_documents_layer_boundary() -> None:
    skill = (ROOT / "skills" / "donegate" / "SKILL.md").read_text(encoding="utf-8")
    metadata = (ROOT / "skills" / "donegate" / "agents" / "openai.yaml").read_text(encoding="utf-8")

    assert "name: donegate" in skill
    assert "Skill is the host operating protocol" in skill
    assert "CLI is the mandatory control plane" in skill
    assert "MCP is an optional structured agent adapter" in skill
    assert "Plugin is the host packaging shell" in skill
    assert "Hooks are triggers" in skill
    assert 'default_prompt: "Use $donegate' in metadata
    assert "allow_implicit_invocation: true" in metadata
