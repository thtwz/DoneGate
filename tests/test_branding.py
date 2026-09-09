from pathlib import Path
import re
import tomllib
import pytest

from donegate_mcp.cli.main import build_parser, main

ROOT = Path(__file__).resolve().parents[1]


def test_distribution_and_primary_cli_use_donegate():
    project = tomllib.loads((ROOT / "pyproject.toml").read_text())["project"]
    assert project["name"] == "donegate"
    assert project["scripts"]["donegate"] == "donegate_mcp.cli.main:main"
    assert project["scripts"]["donegate-mcp"] == project["scripts"]["donegate"]
    assert build_parser().prog == "donegate"


def test_serve_subcommand_dispatches_without_creating_project(tmp_path, monkeypatch):
    from donegate_mcp.mcp import server
    calls = []
    monkeypatch.setattr(server, "main", lambda **kw: calls.append(kw) or 0)
    monkeypatch.chdir(tmp_path)
    assert main(["serve"]) == 0
    assert calls == [{"data_root": None, "repo_root": None}]
    assert not (tmp_path / ".donegate-mcp").exists()


@pytest.mark.parametrize("target_flag", ["--repo-root", "--data-root"])
def test_serve_explicit_target_overrides_environment_and_allows_per_call_target(tmp_path, monkeypatch, target_flag):
    from donegate_mcp.mcp import server
    inherited, explicit, override = [tmp_path / name for name in ("inherited", "explicit", "override")]
    for repo in (inherited, explicit, override):
        repo.mkdir()
    monkeypatch.setenv("DONEGATE_MCP_REPO_ROOT", str(inherited))
    monkeypatch.setenv("DONEGATE_MCP_ROOT", str(inherited / ".donegate-mcp"))
    captured = []
    def build_server(app):
        adapter = server.SimpleToolServer()
        adapter.run = lambda: captured.append(app)
        return adapter
    monkeypatch.setattr(server.DoneGateMcpApp, "_build_server", build_server)
    target = explicit if target_flag == "--repo-root" else explicit / ".donegate-mcp"
    assert main([target_flag, str(target), "serve"]) == 0
    service, _ = captured[0]._resolve_call_context()
    assert service.data_root == explicit / ".donegate-mcp"
    service, repo = captured[0]._resolve_call_context(repo_root=str(override))
    assert service.data_root == override / ".donegate-mcp"
    assert repo == str(override)


def test_current_guides_recommend_canonical_commands():
    paths = [ROOT / p for p in ["README.md", "README.zh-CN.md", "docs/startup-guide.md",
             "docs/end-to-end-demo.md", "docs/release-checklist.md", "skills/donegate/references/operations.md"]]
    legacy_usage = re.compile(r"(?<![\w./-])donegate-mcp(?:-serve)?(?=\s+(?:--|ui|task|bootstrap|init|serve))")
    assert not [str(p.relative_to(ROOT)) for p in paths if legacy_usage.search(p.read_text())]


def test_generated_onboarding_recommends_donegate(tmp_path):
    from donegate_mcp.domain.services import DoneGateService
    import subprocess
    subprocess.run(["git", "init", str(tmp_path)], capture_output=True, check=True)
    service = DoneGateService(tmp_path / ".donegate-mcp", repo_root=tmp_path)
    service.bootstrap_repository("DoneGate example", repo_root=tmp_path)
    text = (service.data_root / "onboarding" / "codex.md").read_text()
    assert "`donegate --json onboarding" in text
    assert "donegate-mcp --" not in text
    next_step = service.get_onboarding(repo_root=tmp_path)["onboarding"]["recommended_next_step"]
    assert "donegate-mcp --" not in next_step
    assert "--data-root" not in next_step
