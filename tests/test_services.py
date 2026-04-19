from __future__ import annotations

import json

from delivery_mcp.domain.services import DeliveryService


def test_init_and_create_task_persists_files(tmp_path) -> None:
    service = DeliveryService(tmp_path / ".delivery-mcp")
    init_payload = service.init_project("demo")
    assert init_payload["ok"] is True

    create_payload = service.create_task("Gate task", "docs/spec.md", summary="summary")
    assert create_payload["task"]["task_id"] == "TASK-0001"

    task_file = tmp_path / ".delivery-mcp" / "tasks" / "TASK-0001.json"
    event_file = tmp_path / ".delivery-mcp" / "events" / "TASK-0001.jsonl"
    plan_file = tmp_path / ".delivery-mcp" / "plan.json"
    progress_file = tmp_path / ".delivery-mcp" / "progress.json"
    assert task_file.exists()
    assert event_file.exists()
    assert plan_file.exists()
    assert progress_file.exists()


def test_service_gate_flow(tmp_path) -> None:
    root = tmp_path / ".delivery-mcp"
    docs = tmp_path / "docs"
    reports = tmp_path / "reports"
    docs.mkdir()
    reports.mkdir()
    (docs / "plan.md").write_text("ok", encoding="utf-8")
    (reports / "pytest.txt").write_text("ok", encoding="utf-8")
    service = DeliveryService(root)
    service.init_project("demo")
    created = service.create_task("Gate task", "docs/spec.md", required_doc_refs=[str(docs / 'plan.md')], required_artifacts=[str(reports / 'pytest.txt')])
    task_id = created["task"]["task_id"]

    service.transition_task(task_id, "ready")
    service.transition_task(task_id, "in_progress")
    service.transition_task(task_id, "awaiting_verification")
    service.record_verification(task_id, "passed", ref=str(reports / 'pytest.txt'))
    service.record_doc_sync(task_id, "synced", ref=str(docs / 'plan.md'))
    closed = service.transition_task(task_id, "done")

    assert closed["task"]["status"] == "done"
    assert closed["task"]["last_verification_ref"] == str(reports / 'pytest.txt')
    assert closed["task"]["last_doc_sync_ref"] == str(docs / 'plan.md')


def test_service_gate_flow_is_order_independent_for_verification_and_doc_sync(tmp_path) -> None:
    root = tmp_path / ".delivery-mcp"
    docs = tmp_path / "docs"
    reports = tmp_path / "reports"
    docs.mkdir()
    reports.mkdir()
    (docs / "plan.md").write_text("ok", encoding="utf-8")
    (reports / "pytest.txt").write_text("ok", encoding="utf-8")
    service = DeliveryService(root)
    service.init_project("demo")
    created = service.create_task("Gate task", "docs/spec.md", required_doc_refs=[str(docs / 'plan.md')], required_artifacts=[str(reports / 'pytest.txt')])
    task_id = created["task"]["task_id"]

    service.transition_task(task_id, "ready")
    service.transition_task(task_id, "in_progress")
    service.transition_task(task_id, "awaiting_verification")
    service.record_doc_sync(task_id, "synced", ref=str(docs / 'plan.md'))
    verified = service.record_verification(task_id, "passed", ref=str(reports / 'pytest.txt'))

    assert verified["task"]["status"] == "documented"
    closed = service.transition_task(task_id, "done")
    assert closed["task"]["status"] == "done"


def test_transition_to_verified_returns_compatibility_warning(tmp_path) -> None:
    root = tmp_path / ".delivery-mcp"
    service = DeliveryService(root)
    service.init_project("demo")
    created = service.create_task("Compat transition", "docs/spec.md")
    task_id = created["task"]["task_id"]

    service.transition_task(task_id, "ready")
    service.record_verification(task_id, "passed")
    transitioned = service.transition_task(task_id, "verified")

    assert transitioned["task"]["status"] == "verified"
    assert transitioned["task"]["projected_status"] == "verified"
    assert transitioned["task"]["status_source"] == "projected"
    assert transitioned["warnings"] == [
        "target_status=verified is a compatibility alias; prefer intent commands plus fact recording"
    ]


def test_list_tasks_normalizes_stale_persisted_status(tmp_path) -> None:
    root = tmp_path / ".delivery-mcp"
    service = DeliveryService(root)
    service.init_project("demo")
    created = service.create_task("Stale task", "docs/spec.md")
    task_id = created["task"]["task_id"]

    task_file = root / "tasks" / f"{task_id}.json"
    payload = json.loads(task_file.read_text(encoding="utf-8"))
    payload["status"] = "awaiting_verification"
    payload["verification_status"] = "passed"
    payload["doc_sync_status"] = "synced"
    payload["started_at"] = payload["created_at"]
    task_file.write_text(json.dumps(payload), encoding="utf-8")

    listed = service.list_tasks()
    assert listed["tasks"][0]["status"] == "documented"

    reloaded = json.loads(task_file.read_text(encoding="utf-8"))
    assert reloaded["status"] == "documented"


def test_dashboard_is_fact_driven_even_when_task_file_is_stale(tmp_path) -> None:
    root = tmp_path / ".delivery-mcp"
    service = DeliveryService(root)
    service.init_project("demo")
    created = service.create_task("Needs docs", "docs/spec.md")
    task_id = created["task"]["task_id"]

    task_file = root / "tasks" / f"{task_id}.json"
    payload = json.loads(task_file.read_text(encoding="utf-8"))
    payload["status"] = "awaiting_verification"
    payload["verification_status"] = "passed"
    payload["started_at"] = payload["created_at"]
    task_file.write_text(json.dumps(payload), encoding="utf-8")

    dashboard = service.dashboard()
    assert dashboard["dashboard"]["missing_verification"] == []
    assert [task["task_id"] for task in dashboard["dashboard"]["missing_docs"]] == [task_id]
    assert dashboard["dashboard"]["counts_by_status"]["verified"] == 1
