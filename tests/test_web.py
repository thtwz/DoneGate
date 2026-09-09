import json
import subprocess
from concurrent.futures import ThreadPoolExecutor

import pytest

from donegate_mcp.domain.services import DoneGateService
from donegate_mcp.errors import ValidationError


def make_project(tmp_path, name="Project"):
    tmp_path.mkdir(parents=True, exist_ok=True)
    subprocess.run(["git", "init", str(tmp_path)], check=True, capture_output=True)
    (tmp_path / ".gitignore").write_text(".donegate-mcp/\n")
    spec = tmp_path / "spec.md"
    spec.write_text("First requirement\n")
    service = DoneGateService(tmp_path / ".donegate-mcp", repo_root=tmp_path)
    service.init_project(name, repo_root=tmp_path)
    return service, spec


def files(root):
    return {str(p.relative_to(root)): p.read_bytes() for p in root.rglob("*") if p.is_file()}


def test_registry_restart_duplicate_ids_and_failed_project_isolation(tmp_path):
    from donegate_mcp.web.registry import ProjectRegistry
    from donegate_mcp.web.read_model import portfolio, project_detail
    a, sa = make_project(tmp_path / "a", "Same")
    b, sb = make_project(tmp_path / "b", "Same")
    a.create_task("A feature", str(sa))
    b.create_task("B feature", str(sb))
    registry = ProjectRegistry(tmp_path / "registry.json")
    ra = registry.add(str(sa.parent))
    rb = registry.add(str(sb.parent))
    assert ra["key"] != rb["key"]
    assert registry.add(str(sa.parent))["key"] == ra["key"]
    assert len(ProjectRegistry(registry.path).list()) == 2
    assert project_detail(ra)["tasks"][0]["title"] == "A feature"
    assert project_detail(rb)["tasks"][0]["title"] == "B feature"
    (sa.parent / ".donegate-mcp" / "project.json").unlink()
    rows = portfolio(registry)["projects"]
    assert rows[0]["error"]
    assert rows[1]["summary"]["total_tasks"] == 1
    registry.remove(ra["key"])
    assert len(registry.list()) == 1
    assert sa.exists()


def test_registry_rejects_missing_mismatched_and_replaced_project(tmp_path):
    from donegate_mcp.web.registry import ProjectRegistry
    from donegate_mcp.web.read_model import project_detail
    a, sa = make_project(tmp_path / "a")
    b, sb = make_project(tmp_path / "b")
    registry = ProjectRegistry(tmp_path / "registry.json")
    with pytest.raises(ValidationError):
        registry.add(str(tmp_path / "missing"))
    with pytest.raises(ValidationError):
        registry.add(str(sa.parent), str(b.data_root))
    row = registry.add(str(sa.parent))
    path = a.data_root / "project.json"
    data = json.loads(path.read_text())
    data["project_id"] = "replacement"
    path.write_text(json.dumps(data))
    with pytest.raises(ValidationError):
        project_detail(row)


def test_reads_do_not_mutate_stale_task_and_compute_truthful_progress(tmp_path):
    from donegate_mcp.web.registry import ProjectRegistry
    from donegate_mcp.web.read_model import project_detail
    service, spec = make_project(tmp_path / "repo")
    task_id = service.create_task("Feature", str(spec))["task"]["task_id"]
    service.transition_task(task_id, "in_progress")
    service.transition_task(task_id, "awaiting_verification")
    service.record_verification(task_id, "passed")
    service.record_doc_sync(task_id, "synced")
    service.transition_task(task_id, "done")
    registry = ProjectRegistry(tmp_path / "registry.json")
    row = registry.add(str(spec.parent))
    assert project_detail(row)["summary"]["completion_rate"] == 100
    spec.write_text("Unrecorded edit\n")
    before = files(service.data_root)
    detail = project_detail(row)
    assert detail["summary"]["done_tasks"] == 1
    assert detail["summary"]["stale_evidence_tasks"] == 1
    assert detail["tasks"][0]["evidence_stale"]
    assert before == files(service.data_root)
    service.refresh_spec(str(spec), reason="Updated requirement")
    detail = project_detail(row)
    assert detail["summary"]["needs_revalidation"] == 1
    change = next(c for c in detail["changes"] if c["version"] == 2)
    assert "-First requirement" in change["diff"]
    assert "+Unrecorded edit" in change["diff"]
    assert change["affected_task_ids"] == [task_id]
    assert change["history_available"]
    assert len(detail["changes"]) == 2  # snapshot + revision; no duplicate drift row


def test_empty_project_and_concurrent_registry_updates(tmp_path):
    from donegate_mcp.web.registry import ProjectRegistry
    from donegate_mcp.web.read_model import project_detail
    projects = [make_project(tmp_path / str(i)) for i in range(5)]
    path = tmp_path / "registry.json"
    with ThreadPoolExecutor(max_workers=5) as pool:
        entries = list(pool.map(lambda pair: ProjectRegistry(path).add(str(pair[1].parent)), projects))
    assert len(ProjectRegistry(path).list()) == 5
    assert project_detail(entries[0])["summary"]["completion_rate"] is None


def test_legacy_events_and_deviations_without_body_history(tmp_path):
    from donegate_mcp.web.registry import ProjectRegistry
    from donegate_mcp.web.read_model import project_detail
    service, spec = make_project(tmp_path / "repo")
    task = service.create_task("Legacy", str(spec))["task"]["task_id"]
    service._emit(task, "spec_drift_detected", {"spec_ref": str(spec), "spec_hash": "oldhash", "reason": "Legacy"})
    service.record_deviation(task, "Changed scope", "Additional acceptance required")
    detail = project_detail(ProjectRegistry(tmp_path / "registry.json").add(str(spec.parent)))
    drift = next(c for c in detail["changes"] if c["kind"] == "spec_drift")
    assert not drift["history_available"] and drift["diff"] is None
    assert len([c for c in detail["changes"] if c["kind"] == "deviation"]) == 1


def test_later_drift_is_not_hidden_by_existing_body_snapshot(tmp_path):
    from donegate_mcp.web.registry import ProjectRegistry
    from donegate_mcp.web.read_model import project_detail
    service, spec = make_project(tmp_path / "repo")
    first = service.create_task("Original feature", str(spec))["task"]["task_id"]
    spec.write_text("Expanded requirement\n")
    second = service.create_task("New feature", str(spec))["task"]["task_id"]
    service.refresh_spec(str(spec), reason="Revalidate original scope")
    detail = project_detail(ProjectRegistry(tmp_path / "registry.json").add(str(spec.parent)))
    revision = next(c for c in detail["changes"] if c["version"] == 2)
    assert revision["affected_task_ids"] == [second]
    drift = [c for c in detail["changes"] if c["kind"] == "spec_drift"]
    assert len(drift) == 1 and drift[0]["affected_task_ids"] == [first]
    assert drift[0]["reason"] == "Revalidate original scope"


def test_diff_preserves_files_without_final_newline(tmp_path):
    from donegate_mcp.web.registry import ProjectRegistry
    from donegate_mcp.web.read_model import project_detail
    service, spec = make_project(tmp_path / "repo")
    spec.write_text("before")
    service.create_task("Feature", str(spec))
    spec.write_text("after")
    service.refresh_spec(str(spec))
    detail = project_detail(ProjectRegistry(tmp_path / "registry.json").add(str(spec.parent)))
    diff = next(c["diff"] for c in detail["changes"] if c["version"] == 2)
    assert "-before\n" in diff and "+after\n" in diff
    assert "\\ No newline at end of file" in diff


@pytest.mark.parametrize("field,value", [("project_name", 123), ("project_id", ["invalid"]), ("project_name", "   ")])
def test_invalid_project_metadata_is_isolated_and_cannot_poison_registry(tmp_path, field, value):
    from donegate_mcp.web.registry import ProjectRegistry
    from donegate_mcp.web.read_model import portfolio
    service, spec = make_project(tmp_path / "repo")
    registry = ProjectRegistry(tmp_path / "registry.json")
    entry = registry.add(str(spec.parent))
    path = service.data_root / "project.json"
    data = json.loads(path.read_text())
    data[field] = value
    path.write_text(json.dumps(data))
    assert portfolio(registry)["projects"][0]["error"]
    with pytest.raises(ValidationError):
        registry.add(str(spec.parent))
    assert registry.list() == [entry]
