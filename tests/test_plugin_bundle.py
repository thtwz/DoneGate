from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_codex_plugin_manifest_references_existing_assets() -> None:
    manifest_path = ROOT / ".codex-plugin" / "plugin.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))

    assert manifest["name"] == "donegate"
    assert manifest["version"] == "0.4.1"
    assert manifest["repository"] == "https://github.com/thtwz/DoneGate"
    assert manifest["license"] == "Apache-2.0"

    for key in ("skills", "hooks"):
        referenced = ROOT / manifest[key]
        assert referenced.exists(), f"{key} path does not exist: {referenced}"

    for key in ("composerIcon", "logo"):
        referenced = ROOT / manifest["interface"][key]
        assert referenced.exists(), f"{key} path does not exist: {referenced}"


def test_codex_plugin_mcp_config_exposes_donegate_server() -> None:
    mcp_config = json.loads((ROOT / ".mcp.json").read_text(encoding="utf-8"))
    server = mcp_config["mcpServers"]["donegate_mcp"]

    assert server["command"] == "${CODEX_PLUGIN_ROOT}/scripts/donegate-mcp-serve-plugin.sh"
    assert server["args"] == []
    assert "env" not in server
