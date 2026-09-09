from __future__ import annotations

import json
import shlex
import subprocess
import sys
from pathlib import Path

import pytest

from donegate_mcp.cli.main import main
from donegate_mcp.cli.formatters import render
from donegate_mcp.compact import compact_payload
from donegate_mcp.domain.services import DoneGateService
from donegate_mcp.mcp.server import DoneGateMcpApp, SimpleToolServer
from donegate_mcp.mcp.tool_schemas import TOOLS


def _tool(app, name):
    if isinstance(app.server, SimpleToolServer):
        return app.server.tools[name]
    return app.server._tool_manager._tools[name].fn


@pytest.fixture
def repo(tmp_path):
    root = tmp_path / "repo"
    root.mkdir()
    subprocess.run(["git", "init", "-b", "main", str(root)], check=True, capture_output=True)
    (root / "spec.md").write_text("Requirements\n")
    (root / "source.py").write_text("value = 1\n")
    service = DoneGateService(data_root=root / ".donegate-mcp", repo_root=root)
    service.init_project("adapter tests", repo_root=root)
    return root


def _cli(repo, capsys, *args):
    code = main(["--repo-root", str(repo), "--json", *args])
    return code, json.loads(capsys.readouterr().out)


def _tasks(repo, commands=None):
    service = DoneGateService(data_root=repo / ".donegate-mcp", repo_root=repo)
    ids = []
    for index, command in enumerate(commands or [f"{shlex.quote(sys.executable)} -c 'print(1)'"] * 2):
        task = service.create_task(f"task {index}", "spec.md", verification_mode="self-test", test_commands=[command], owned_paths=["source.py"])["task"]
        service.transition_task(task["task_id"], "ready")
        ids.append(task["task_id"])
    return ids


def test_cli_batch_flow_reuses_checks_and_preserves_compact_outcomes(repo, capsys):
    ids = _tasks(repo)
    code, created = _cli(repo, capsys, "batch", "create", "--title", "Shared work", "--task-id", ids[0], "--task-id", ids[1], "--dependencies", "{}")
    assert code == 0
    batch_id = created["batch"]["batch_id"]
    for command in ["show", "activate", "start", "submit"]:
        code, payload = _cli(repo, capsys, "batch", command, batch_id)
        assert code == 0 and payload["ok"]
    code, checked = _cli(repo, capsys, "--compact", "batch", "check", batch_id)
    assert code == 0
    assert checked["executed_count"] == 1
    assert checked["reused_count"] == 0
    assert all(task["ok"] and task["errors"] == [] for task in checked["tasks"])
    code, reused = _cli(repo, capsys, "batch", "check", batch_id)
    assert code == 0 and reused["executed_count"] == 0
    assert reused["reused_count"] == 1
    code, forced = _cli(repo, capsys, "batch", "check", batch_id, "--force")
    assert code == 0 and forced["executed_count"] == 1
    assert _cli(repo, capsys, "batch", "list")[1]["batches"][0]["batch_id"] == batch_id
    assert _cli(repo, capsys, "batch", "active")[1]["active_batch"]["batch_id"] == batch_id
    assert _cli(repo, capsys, "batch", "doc-sync", batch_id, "--result", "synced", "--ref", "spec.md")[0] == 0
    assert _cli(repo, capsys, "batch", "done", batch_id)[0] == 0


def test_failed_batch_cli_check_is_nonzero_with_independent_outcomes(repo, capsys):
    ids = _tasks(repo, [f"{shlex.quote(sys.executable)} -c 'exit(1)'", f"{shlex.quote(sys.executable)} -c 'print(1)'"])
    _, created = _cli(repo, capsys, "batch", "create", "--title", "Mixed", "--task-id", ids[0], "--task-id", ids[1])
    code, result = _cli(repo, capsys, "--compact", "batch", "check", created["batch"]["batch_id"])
    assert code != 0
    assert result["ok"] is False and result["errors"]
    assert {task["task_id"]: task["ok"] for task in result["tasks"]} == {ids[0]: False, ids[1]: True}
    assert result["tasks"][0]["errors"]


@pytest.mark.parametrize("contents", ["{broken", '{}', '[{"title":"valid","spec_ref":"spec.md"},42]'])
def test_cli_bulk_invalid_input_returns_json_without_creating_tasks(repo, capsys, contents):
    path = repo / "tasks.json"
    path.write_text(contents)
    code, result = _cli(repo, capsys, "task", "create-many", "--file", str(path))
    assert code == 2 and result["ok"] is False and result["errors"]
    assert DoneGateService(data_root=repo / ".donegate-mcp", repo_root=repo).list_tasks()["tasks"] == []


def test_cli_bulk_and_dependency_file(repo, capsys):
    path = repo / "tasks.json"
    path.write_text(json.dumps([{"title": title, "spec_ref": "spec.md"} for title in ["first", "second"]]))
    code, result = _cli(repo, capsys, "task", "create-many", "--file", str(path))
    assert code == 0
    ids = [task["task_id"] for task in result["tasks"]]
    assert ids == ["TASK-0001", "TASK-0002"]
    assert all("history" not in task for task in result["tasks"])
    deps = repo / "deps.json"
    deps.write_text(json.dumps({ids[1]: [ids[0]]}))
    code, result = _cli(repo, capsys, "batch", "create", "--title", "Ordered", "--task-id", ids[0], "--task-id", ids[1], "--dependencies-file", str(deps), "--mode", "single", "--rationale", "Separate acceptance", "--risk", "high")
    assert code == 0
    assert result["batch"]["dependencies"][ids[1]] == [ids[0]]


def test_batch_mcp_tools_target_explicit_repo_and_keep_failures(repo, tmp_path):
    app = DoneGateMcpApp(data_root=str(tmp_path / "wrong-project"))
    ids = _tasks(repo, [f"{shlex.quote(sys.executable)} -c 'exit(1)'", f"{shlex.quote(sys.executable)} -c 'print(1)'"])
    created = _tool(app, "batch_create")("Mixed", ids, repo_root=str(repo))
    batch_id = created["batch"]["batch_id"]
    assert _tool(app, "batch_get")(batch_id, repo_root=str(repo))["ok"]
    assert _tool(app, "batch_activate")(batch_id, repo_root=str(repo))["ok"]
    assert _tool(app, "batch_active")(repo_root=str(repo))["active_batch"]["batch_id"] == batch_id
    assert _tool(app, "batch_transition")(batch_id, "in_progress", repo_root=str(repo))["ok"]
    checked = _tool(app, "batch_check")(batch_id, repo_root=str(repo), compact=True)
    assert checked["ok"] is False and checked["executed_count"] == 2
    assert checked["tasks"][0]["errors"] and checked["tasks"][1]["ok"]
    assert _tool(app, "batch_record_doc_sync")(batch_id, "synced", ref="spec.md", repo_root=str(repo))["ok"]
    assert len(_tool(app, "batch_list")(repo_root=str(repo))["batches"]) == 1
    assert not (tmp_path / "wrong-project" / "project.json").exists()
    bulk = _tool(app, "task_create_many")([{"title": "another", "spec_ref": "spec.md"}], repo_root=str(repo), compact=True)
    assert bulk["ok"] and bulk["tasks"][0]["task_id"] == "TASK-0003"


def test_batch_tool_schemas_expose_target_and_matching_operations():
    app = DoneGateMcpApp()
    for name in ["batch_create", "batch_list", "batch_get", "batch_activate", "batch_active", "batch_transition", "batch_check", "batch_record_doc_sync", "task_create_many"]:
        assert name in TOOLS
        assert TOOLS[name]["repo_root"] == "str?"
        assert callable(_tool(app, name))


def test_compact_health_and_outcomes_remain_explainable():
    payload = {"ok": False, "executed_count": 1, "reused_count": 2, "tasks": [{"task_id": "TASK-0001", "verification_status": "failed", "ok": False, "errors": ["missing evidence"], "evidence_stale": True, "verification_health": "stale", "history": ["verbose"]}]}
    result = compact_payload(payload)
    assert result["tasks"][0]["ok"] is False
    assert result["tasks"][0]["errors"] == ["missing evidence"]
    assert result["tasks"][0]["evidence_stale"] is True
    assert result["tasks"][0]["verification_health"] == "stale"
    assert "history" not in result["tasks"][0]


def test_human_formatter_shows_active_batch_and_run_counts():
    context = {"ok": True, "context": {"repo_root": "/repo", "branch": "main", "active_batch": {"batch_id": "BATCH-0001", "title": "Shared", "task_ids": ["TASK-0001", "TASK-0002"], "selected_mode": "batch"}, "status": "active", "next_action": "check"}}
    assert "BATCH-0001" in render(context, False)
    report = {"ok": False, "errors": ["one task failed"], "batch": context["context"]["active_batch"], "executed_count": 1, "reused_count": 2, "tasks": [{"task_id": "TASK-0001", "ok": False, "errors": ["command failed"]}, {"task_id": "TASK-0002", "ok": True, "errors": []}]}
    output = render(report, False)
    assert "executed=1" in output and "reused=2" in output
    assert "TASK-0001" in output and "command failed" in output and "TASK-0002" in output


def test_human_formatter_does_not_imply_verification_when_starting_batch():
    payload = {"ok": True, "batch": {"batch_id": "BATCH-0001", "task_ids": ["TASK-0001"]}, "tasks": [{"task_id": "TASK-0001", "ok": True, "errors": [], "verification_status": "pending"}]}
    assert "passed" not in render(payload, False)


def test_human_bulk_formatter_retains_partial_results_and_count():
    payload = {"ok": False, "created_count": 1, "errors": ["write failed"], "tasks": [{"task_id": "TASK-0001", "title": "first", "status": "draft", "ok": True, "errors": []}, {"ok": False, "errors": ["write failed"]}]}
    output = render(payload, False)
    assert "created=1" in output and "TASK-0001" in output and "write failed" in output


def test_compact_retains_persisted_batch_binding():
    task = {"task_id": "TASK-0001", "verification_status": "pending", "batch_id": "BATCH-abc"}
    assert compact_payload(task)["batch_id"] == "BATCH-abc"


@pytest.mark.parametrize("contents", [None, b"{broken", b"\xff"])
def test_cli_json_file_failures_are_structured(repo, capsys, contents):
    path = repo / "input.json"
    if contents is not None:
        path.write_bytes(contents)
    for arguments in [
        ("task", "create-many", "--file", str(path)),
        ("batch", "create", "--title", "Invalid input", "--task-id", "TASK-0001", "--dependencies-file", str(path)),
    ]:
        code, payload = _cli(repo, capsys, *arguments)
        assert code == 2 and payload["ok"] is False
        assert payload["errors"] and "cannot read JSON file" in payload["errors"][0]


def test_bound_task_cli_check_routes_batch_and_self_test_returns_domain_error(repo, capsys):
    ids = _tasks(repo, [f"{shlex.quote(sys.executable)} -c 'exit(1)'", f"{shlex.quote(sys.executable)} -c 'print(1)'"])
    _, created = _cli(repo, capsys, "batch", "create", "--title", "Bound", "--task-id", ids[0], "--task-id", ids[1])
    batch_id = created["batch"]["batch_id"]
    code, checked = _cli(repo, capsys, "--compact", "task", "check", ids[1])
    assert code != 0 and checked["ok"] is False
    assert checked["batch"]["batch_id"] == batch_id
    assert {row["task_id"]: row["ok"] for row in checked["tasks"]} == {ids[0]: False, ids[1]: True}
    code, rejected = _cli(repo, capsys, "task", "self-test", ids[1])
    assert code != 0 and rejected["ok"] is False and rejected["errors"]
    app = DoneGateMcpApp()
    rejection = _tool(app, "task_run_self_test")(ids[1], repo_root=str(repo))
    assert rejection["ok"] is False and rejection["errors"]
    shown = _tool(app, "task_get")(ids[1], repo_root=str(repo))
    assert compact_payload(shown)["task"]["batch_id"] == batch_id


@pytest.mark.parametrize("contents", [b"{broken", b"[]", b"\xff"])
def test_corrupt_batch_definition_returns_structured_cli_and_mcp_errors(repo, capsys, contents):
    ids = _tasks(repo)
    _, created = _cli(repo, capsys, "batch", "create", "--title", "Corrupt fixture", "--task-id", ids[0])
    batch_id = created["batch"]["batch_id"]
    definition = repo / ".donegate-mcp" / "batches" / f"{batch_id}.json"
    definition.write_bytes(contents)
    code, payload = _cli(repo, capsys, "batch", "show", batch_id)
    assert code != 0 and payload["ok"] is False and payload["errors"]
    app = DoneGateMcpApp()
    payload = _tool(app, "batch_get")(batch_id, repo_root=str(repo))
    assert payload["ok"] is False and payload["errors"]
