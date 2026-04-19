from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path


def run_cli(tmp_path, *args: str) -> subprocess.CompletedProcess[str]:
    cmd = [sys.executable, "-m", "delivery_mcp.cli.main", "--data-root", str(tmp_path / ".delivery-mcp"), *args]
    return subprocess.run(cmd, capture_output=True, text=True, check=False)


def test_done_returns_gate_violation_exit_code(tmp_path) -> None:
    assert run_cli(tmp_path, "init", "--project-name", "demo").returncode == 0
    created = run_cli(tmp_path, "--json", "task", "create", "--title", "t", "--spec-ref", "docs/spec.md")
    task_id = json.loads(created.stdout)["task"]["task_id"]
    assert run_cli(tmp_path, "task", "done", task_id).returncode == 3


def test_json_dashboard_output(tmp_path) -> None:
    run_cli(tmp_path, "init", "--project-name", "demo")
    out = run_cli(tmp_path, "--json", "dashboard")
    payload = json.loads(out.stdout)
    assert payload["ok"] is True
    assert payload["dashboard"]["project_name"] == "demo"


def test_cli_self_test_command(tmp_path) -> None:
    run_cli(tmp_path, "init", "--project-name", "demo")
    created = run_cli(tmp_path, "--json", "task", "create", "--title", "t", "--spec-ref", "docs/spec.md", "--verification-mode", "self-test", "--test-command", "python3 -c 'print(1)'", "--plan-node-id", "node-1")
    task_id = json.loads(created.stdout)["task"]["task_id"]
    run_cli(tmp_path, "task", "transition", task_id, "--to", "ready")
    run_cli(tmp_path, "task", "start", task_id)
    run_cli(tmp_path, "task", "submit", task_id)
    tested = run_cli(tmp_path, "--json", "task", "self-test", task_id, "--workdir", str(tmp_path))
    payload = json.loads(tested.stdout)
    assert payload["task"]["verification_status"] == "passed"
    assert payload["exit_code"] == 0


def test_cli_plan_progress_and_spec_drift(tmp_path) -> None:
    spec = tmp_path / "spec.md"
    spec.write_text("v1", encoding="utf-8")
    run_cli(tmp_path, "init", "--project-name", "demo")
    created = run_cli(tmp_path, "--json", "task", "create", "--title", "t", "--spec-ref", str(spec), "--plan-node-id", "node-a")
    task_id = json.loads(created.stdout)["task"]["task_id"]
    spec.write_text("v2", encoding="utf-8")
    refreshed = json.loads(run_cli(tmp_path, "--json", "spec", "refresh", "--spec-ref", str(spec), "--reason", "spec updated").stdout)
    assert task_id in refreshed["changed_tasks"]
    plan = json.loads(run_cli(tmp_path, "--json", "plan").stdout)
    progress = json.loads(run_cli(tmp_path, "--json", "progress").stdout)
    assert plan["plan"]["nodes"][0]["needs_revalidation"] is True
    assert progress["progress"]["stale_tasks"][0]["task_id"] == task_id


def test_cli_deviation_roundtrip(tmp_path) -> None:
    run_cli(tmp_path, "init", "--project-name", "demo")
    created = run_cli(tmp_path, "--json", "task", "create", "--title", "t", "--spec-ref", "docs/spec.md")
    task_id = json.loads(created.stdout)["task"]["task_id"]
    run_cli(tmp_path, "deviation", "add", task_id, "--summary", "changed behavior", "--details", "temporary divergence")
    listed = json.loads(run_cli(tmp_path, "--json", "deviation", "list").stdout)
    assert listed["deviations"][0]["task_id"] == task_id


def test_submit_intent_can_move_ready_task_into_awaiting_verification(tmp_path) -> None:
    run_cli(tmp_path, "init", "--project-name", "demo")
    created = run_cli(tmp_path, "--json", "task", "create", "--title", "t", "--spec-ref", "docs/spec.md")
    task_id = json.loads(created.stdout)["task"]["task_id"]
    run_cli(tmp_path, "task", "transition", task_id, "--to", "ready")
    submitted = json.loads(run_cli(tmp_path, "--json", "task", "submit", task_id).stdout)
    assert submitted["task"]["status"] == "awaiting_verification"
    assert submitted["task"]["started_at"] is not None


def test_transition_verified_is_compatibility_alias_for_fact_projected_state(tmp_path) -> None:
    run_cli(tmp_path, "init", "--project-name", "demo")
    created = run_cli(tmp_path, "--json", "task", "create", "--title", "t", "--spec-ref", "docs/spec.md")
    task_id = json.loads(created.stdout)["task"]["task_id"]
    run_cli(tmp_path, "task", "transition", task_id, "--to", "ready")
    run_cli(tmp_path, "task", "verify", task_id, "--result", "passed")
    transitioned = json.loads(run_cli(tmp_path, "--json", "task", "transition", task_id, "--to", "verified").stdout)
    assert transitioned["task"]["status"] == "verified"
    assert transitioned["task"]["projected_status"] == "verified"
    assert transitioned["task"]["status_source"] == "projected"
    assert transitioned["task"]["started_at"] is not None
    assert transitioned["warnings"] == [
        "target_status=verified is a compatibility alias; prefer intent commands plus fact recording"
    ]


def test_done_intent_can_close_ready_task_once_facts_are_satisfied(tmp_path) -> None:
    run_cli(tmp_path, "init", "--project-name", "demo")
    doc = tmp_path / "plan.md"
    artifact = tmp_path / "artifact.txt"
    doc.write_text("ok", encoding="utf-8")
    artifact.write_text("ok", encoding="utf-8")
    created = run_cli(
        tmp_path,
        "--json",
        "task",
        "create",
        "--title",
        "t",
        "--spec-ref",
        "docs/spec.md",
        "--required-doc-ref",
        str(doc),
        "--required-artifact",
        str(artifact),
    )
    task_id = json.loads(created.stdout)["task"]["task_id"]
    run_cli(tmp_path, "task", "transition", task_id, "--to", "ready")
    run_cli(tmp_path, "task", "verify", task_id, "--result", "passed", "--ref", str(artifact))
    run_cli(tmp_path, "task", "doc-sync", task_id, "--result", "synced", "--ref", str(doc))
    closed = json.loads(run_cli(tmp_path, "--json", "task", "done", task_id).stdout)
    assert closed["task"]["status"] == "done"
