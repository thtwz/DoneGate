from __future__ import annotations

from pathlib import Path

from donegate_mcp.mcp.server import DoneGateMcpApp, SimpleToolServer


def test_mcp_app_prefers_donegate_env_repo_root_over_server_default_data_root(tmp_path, monkeypatch) -> None:
    server_home = tmp_path / "server-home"
    target_repo = tmp_path / "target-repo"
    target_repo.mkdir()
    monkeypatch.setenv("DONEGATE_MCP_REPO_ROOT", str(target_repo))

    app = DoneGateMcpApp(data_root=str(server_home / ".donegate-mcp"))
    assert isinstance(app.server, SimpleToolServer)

    payload = app.server.tools["project_init"]("demo")

    assert payload["ok"] is True
    assert (target_repo / ".donegate-mcp" / "project.json").exists()
    assert not (server_home / ".donegate-mcp" / "project.json").exists()


def test_mcp_tools_accept_repo_root_override_for_target_repository(tmp_path) -> None:
    server_home = tmp_path / "server-home"
    target_repo = tmp_path / "target-repo"
    target_repo.mkdir()

    app = DoneGateMcpApp(data_root=str(server_home / ".donegate-mcp"))
    assert isinstance(app.server, SimpleToolServer)

    init_payload = app.server.tools["project_init"]("demo", repo_root=str(target_repo))
    create_payload = app.server.tools["task_create"](
        "Gate task",
        "docs/spec.md",
        repo_root=str(target_repo),
    )

    assert init_payload["ok"] is True
    assert create_payload["ok"] is True
    assert create_payload["task"]["spec_ref"] == str((target_repo / "docs" / "spec.md").resolve())
    assert (target_repo / ".donegate-mcp" / "project.json").exists()
    assert not (server_home / ".donegate-mcp" / "project.json").exists()
