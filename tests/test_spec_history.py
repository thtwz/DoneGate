import subprocess

from donegate_mcp.domain.services import DoneGateService


def project(tmp_path):
    subprocess.run(["git", "init", str(tmp_path)], check=True, capture_output=True)
    spec = tmp_path / "spec.md"
    spec.write_text("# Login\nPassword login\n")
    service = DoneGateService(tmp_path / ".donegate-mcp", repo_root=tmp_path)
    service.init_project("History", repo_root=tmp_path)
    task = service.create_task("Login", str(spec))["task"]
    return service, spec, task["task_id"]


def test_requirement_versions_capture_content_and_reverts(tmp_path):
    service, spec, task_id = project(tmp_path)
    spec.write_text("# Login\nPasskey login\n")
    changed = service.refresh_spec(str(spec), reason="Support passkeys")
    assert changed["spec_version"] == 2
    assert changed["changed_tasks"] == [task_id]
    assert service.get_task(task_id)["task"]["needs_revalidation"]
    assert service.refresh_spec(str(spec))["changed_tasks"] == []
    spec.write_text("# Login\nPassword login\n")
    assert service.refresh_spec(str(spec), reason="Revert")["spec_version"] == 3
    from donegate_mcp.storage.spec_store import SpecStore
    rows = SpecStore(service.data_root).list()
    assert [row["version"] for row in rows] == [1, 2, 3]
    assert rows[1]["reason"] == "Support passkeys"
    assert rows[1]["affected_task_ids"] == [task_id]
    assert rows[0]["content"] == rows[2]["content"]
    assert rows[1]["previous_hash"] == rows[0]["spec_hash"]


def test_legacy_first_refresh_does_not_invent_previous_content(tmp_path):
    service, spec, task_id = project(tmp_path)
    # Simulate an older installation's tasks without any saved body snapshots.
    for path in (service.data_root / "spec-history").glob("*.json"):
        path.unlink()
    spec.write_text("New requirements\n")
    service.refresh_spec(str(spec), reason="First tracked change")
    from donegate_mcp.storage.spec_store import SpecStore
    rows = SpecStore(service.data_root).list()
    assert len(rows) == 1
    assert rows[0]["previous_hash"] is None
    assert rows[0]["affected_task_ids"] == [task_id]


def test_refresh_missing_spec_does_not_add_history(tmp_path):
    import pytest
    from donegate_mcp.errors import ValidationError
    service, spec, _ = project(tmp_path)
    before = {str(p): p.read_bytes() for p in (service.data_root / "spec-history").glob("*.json")}
    spec.unlink()
    with pytest.raises(ValidationError):
        service.refresh_spec(str(spec))
    assert before == {str(p): p.read_bytes() for p in (service.data_root / "spec-history").glob("*.json")}
