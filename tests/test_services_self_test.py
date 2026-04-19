from __future__ import annotations

from pathlib import Path

from donegate_mcp.domain.services import DoneGateService
from donegate_mcp.errors import TransitionError


def test_self_test_passes_and_records_artifacts(tmp_path) -> None:
    root = tmp_path / ".donegate-mcp"
    service = DoneGateService(root)
    service.init_project("demo")
    created = service.create_task("Gate task", "docs/spec.md", verification_mode="self-test", test_commands=["python3 -c 'print(123)'"])
    task_id = created["task"]["task_id"]
    service.transition_task(task_id, "ready")
    service.transition_task(task_id, "in_progress")
    service.transition_task(task_id, "awaiting_verification")
    result = service.run_self_test(task_id, workdir=str(tmp_path))
    assert result["task"]["verification_status"] == "passed"
    assert result["exit_code"] == 0
    assert result["self_test"]["stdout_path"].endswith('.stdout.log')


def test_self_test_failure_marks_verification_failed(tmp_path) -> None:
    root = tmp_path / ".donegate-mcp"
    service = DoneGateService(root)
    service.init_project("demo")
    created = service.create_task("Gate task", "docs/spec.md", verification_mode="self-test", test_commands=["python3 -c 'import sys; sys.exit(7)'"])
    task_id = created["task"]["task_id"]
    service.transition_task(task_id, "ready")
    service.transition_task(task_id, "in_progress")
    service.transition_task(task_id, "awaiting_verification")
    result = service.run_self_test(task_id, workdir=str(tmp_path))
    assert result["task"]["verification_status"] == "failed"
    assert result["task"]["status"] == "in_progress"
    assert result["exit_code"] == 7


def test_done_requires_existing_artifacts_and_doc_refs(tmp_path) -> None:
    root = tmp_path / ".donegate-mcp"
    service = DoneGateService(root)
    service.init_project("demo")
    doc = tmp_path / "docs" / "plan.md"
    doc.parent.mkdir(parents=True, exist_ok=True)
    doc.write_text("ok", encoding="utf-8")
    created = service.create_task("Gate task", "docs/spec.md", required_doc_refs=[str(doc)], required_artifacts=[str(tmp_path / 'reports' / 'pytest.txt')])
    task_id = created["task"]["task_id"]
    service.transition_task(task_id, "ready")
    service.transition_task(task_id, "in_progress")
    service.transition_task(task_id, "awaiting_verification")
    service.record_verification(task_id, "passed", ref="x")
    service.record_doc_sync(task_id, "synced", ref=str(doc))
    try:
        service.transition_task(task_id, "done")
    except TransitionError as exc:
        assert "missing required artifacts" in str(exc)
    else:
        raise AssertionError('expected artifact gate failure')


def test_plan_progress_and_spec_drift(tmp_path) -> None:
    root = tmp_path / ".donegate-mcp"
    spec = tmp_path / "spec.md"
    spec.write_text("v1", encoding="utf-8")
    service = DoneGateService(root)
    service.init_project("demo")
    created = service.create_task("Gate task", str(spec), plan_node_id="phase-1-task-a")
    task_id = created["task"]["task_id"]
    spec.write_text("v2", encoding="utf-8")
    refreshed = service.refresh_spec(str(spec), reason="spec changed")
    assert task_id in refreshed["changed_tasks"]
    plan = service.get_plan()["plan"]
    progress = service.get_progress()["progress"]
    assert plan["nodes"][0]["needs_revalidation"] is True
    assert progress["stale_tasks"][0]["task_id"] == task_id


def test_deviation_recording(tmp_path) -> None:
    root = tmp_path / ".donegate-mcp"
    service = DoneGateService(root)
    service.init_project("demo")
    created = service.create_task("Gate task", "docs/spec.md")
    task_id = created["task"]["task_id"]
    service.record_deviation(task_id, "changed behavior", "temporary divergence")
    listed = service.list_deviations()["deviations"]
    assert listed[0]["task_id"] == task_id
    assert listed[0]["summary"] == "changed behavior"
