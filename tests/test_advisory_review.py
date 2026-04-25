from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from donegate_mcp.domain.services import DoneGateService


def _run_cli(data_root: Path, *args: str) -> subprocess.CompletedProcess[str]:
    cmd = [
        sys.executable,
        "-m",
        "donegate_mcp.cli.main",
        "--data-root",
        str(data_root),
        *args,
    ]
    return subprocess.run(cmd, capture_output=True, text=True, check=False)


def test_submit_and_done_create_advisory_review_requests(tmp_path) -> None:
    root = tmp_path / ".donegate-mcp"
    docs = tmp_path / "docs"
    docs.mkdir()
    (docs / "spec.md").write_text("v1\n", encoding="utf-8")
    (docs / "plan.md").write_text("ok\n", encoding="utf-8")

    service = DoneGateService(root)
    service.init_project("demo", repo_root=str(tmp_path))
    task_id = service.create_task(
        "Gate task",
        "docs/spec.md",
        required_doc_refs=["docs/plan.md"],
    )["task"]["task_id"]

    service.transition_task(task_id, "ready")
    submitted = service.transition_task(task_id, "awaiting_verification")
    submit_summary = submitted["task"]["advisory_summary"]
    assert submit_summary["pending_reviews"] == 1

    reviews = service.list_reviews(task_id=task_id, include_findings=True)
    assert reviews["reviews"][0]["checkpoint"] == "submit"
    assert reviews["reviews"][0]["status"] == "requested"
    assert "architect" in reviews["reviews"][0]["request_hint"].lower()

    service.record_verification(task_id, "passed", ref="reports/pytest.txt")
    service.record_doc_sync(task_id, "synced", ref=str((docs / "plan.md").resolve()))
    closed = service.transition_task(task_id, "done")

    assert closed["task"]["status"] == "done"
    assert closed["task"]["advisory_summary"]["pending_reviews"] == 2
    review_payload = service.list_reviews(task_id=task_id, include_findings=True)
    assert {run["checkpoint"] for run in review_payload["reviews"]} == {"submit", "pre_done"}


def test_repeated_submit_and_done_do_not_duplicate_advisory_review_requests(tmp_path) -> None:
    root = tmp_path / ".donegate-mcp"
    docs = tmp_path / "docs"
    docs.mkdir()
    (docs / "spec.md").write_text("v1\n", encoding="utf-8")

    service = DoneGateService(root)
    service.init_project("demo", repo_root=str(tmp_path))
    task_id = service.create_task("Gate task", "docs/spec.md")["task"]["task_id"]

    service.transition_task(task_id, "ready")
    service.transition_task(task_id, "in_progress")
    service.transition_task(task_id, "awaiting_verification")
    service.transition_task(task_id, "awaiting_verification")

    submit_reviews = service.list_reviews(task_id=task_id, checkpoint="submit")["reviews"]
    assert len(submit_reviews) == 1

    service.record_verification(task_id, "passed", ref="reports/pytest.txt")
    service.record_doc_sync(task_id, "synced", ref=str((docs / "spec.md").resolve()))
    service.transition_task(task_id, "done")
    service.transition_task(task_id, "done")

    pre_done_reviews = service.list_reviews(task_id=task_id, checkpoint="pre_done")["reviews"]
    assert len(pre_done_reviews) == 1


def test_review_run_preserves_requested_and_completed_provider_audit(tmp_path) -> None:
    root = tmp_path / ".donegate-mcp"
    docs = tmp_path / "docs"
    docs.mkdir()
    (docs / "spec.md").write_text("v1\n", encoding="utf-8")

    service = DoneGateService(root)
    service.init_project("demo", repo_root=str(tmp_path))
    task_id = service.create_task("Gate task", "docs/spec.md")["task"]["task_id"]
    service.transition_task(task_id, "ready")
    service.transition_task(task_id, "awaiting_verification")

    requested = service.list_reviews(task_id=task_id, checkpoint="submit")["reviews"][0]
    assert requested["provider_id"] == "host_skill"
    assert requested["requested_provider_id"] == "host_skill"
    assert requested["completed_provider_id"] is None

    reviewed = service.record_task_review(
        task_id,
        checkpoint="submit",
        provider_id="manual",
        review_run_id=requested["review_run_id"],
        summary="Manual reviewer completed a host-skill requested review.",
    )

    assert reviewed["review"]["provider_id"] == "manual"
    assert reviewed["review"]["requested_provider_id"] == "host_skill"
    assert reviewed["review"]["completed_provider_id"] == "manual"


def test_record_review_and_spawn_followup_task_updates_dashboard_and_supervision(tmp_path) -> None:
    repo = tmp_path / "repo"
    docs = repo / "docs"
    repo.mkdir()
    docs.mkdir()
    subprocess.run(["git", "init"], cwd=repo, check=True, capture_output=True, text=True)
    subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=repo, check=True, capture_output=True, text=True)
    subprocess.run(["git", "config", "user.name", "Test User"], cwd=repo, check=True, capture_output=True, text=True)
    tracked = repo / "tracked.txt"
    tracked.write_text("v1\n", encoding="utf-8")
    (docs / "spec.md").write_text("v1\n", encoding="utf-8")
    subprocess.run(["git", "add", "tracked.txt", "docs/spec.md"], cwd=repo, check=True, capture_output=True, text=True)
    subprocess.run(["git", "commit", "-m", "init"], cwd=repo, check=True, capture_output=True, text=True)
    tracked.write_text("v2\n", encoding="utf-8")

    service = DoneGateService(repo / ".donegate-mcp")
    service.init_project("demo", repo_root=str(repo))
    task_id = service.create_task("Gate task", "docs/spec.md", owned_paths=["tracked.txt"])["task"]["task_id"]
    service.activate_task(task_id, repo_root=repo)
    service.transition_task(task_id, "ready")
    service.transition_task(task_id, "awaiting_verification")

    recorded = service.record_task_review(
        task_id,
        checkpoint="submit",
        provider_id="manual",
        summary="This only satisfies the literal flow, not the user intent.",
        overall_recommendation="proceed_with_followups",
        findings=[
            {
                "dimension": "outcome_gap",
                "severity": "high",
                "title": "Missing real-world batch workflow",
                "details": "The flow covers only one item at a time, but users need batch execution.",
                "recommended_action": "Add a batch workflow and make it discoverable.",
                "suggested_task_title": "Add batch workflow for gate task",
                "suggested_task_summary": "Extend the accepted flow so users can process multiple items in one pass.",
                "suggested_owned_paths": ["tracked.txt"],
            }
        ],
    )

    finding_id = recorded["findings"][0]["finding_id"]
    assert recorded["task"]["advisory_summary"]["pending_reviews"] == 0
    followup = service.create_followup_task_from_finding(finding_id)

    assert followup["task"]["source_finding_id"] == finding_id
    assert followup["task"]["source_task_id"] == task_id
    assert followup["task"]["parent_task_id"] == task_id

    dashboard = service.dashboard(include_tasks=True)
    assert dashboard["dashboard"]["open_advisories"] == 0
    assert dashboard["dashboard"]["high_severity_advisories"] == 0
    assert dashboard["dashboard"]["followup_spawned_advisories"] == 1
    assert dashboard["dashboard"]["tasks_with_open_advisories"] == []

    supervision = service.get_supervision(repo_root=repo)
    assert supervision["supervision"]["advisory_summary"]["open_advisories"] == 0
    assert supervision["supervision"]["advisory_summary"]["high_severity_advisories"] == 0
    assert supervision["supervision"]["advisory_summary"]["followup_spawned_advisories"] == 1
    assert supervision["supervision"]["active_task"]["advisory_summary"]["open_advisories"] == 0

    findings = service.list_reviews(task_id=task_id, include_findings=True)["findings"]
    assert findings[0]["disposition"] == "spawned_followup"
    assert findings[0]["followup_task_id"] == followup["task"]["task_id"]


def test_cli_review_flow_records_finding_and_creates_followup_task(tmp_path) -> None:
    root = tmp_path / ".donegate-mcp"
    docs = tmp_path / "docs"
    docs.mkdir()
    (docs / "spec.md").write_text("v1\n", encoding="utf-8")

    assert _run_cli(root, "init", "--project-name", "demo", "--repo-root", str(tmp_path)).returncode == 0
    created = json.loads(
        _run_cli(
            root,
            "--json",
            "task",
            "create",
            "--title",
            "Gate task",
            "--spec-ref",
            "docs/spec.md",
        ).stdout
    )
    task_id = created["task"]["task_id"]

    finding = json.dumps(
        {
            "dimension": "outcome_gap",
            "severity": "medium",
            "title": "Users still need a faster path",
            "details": "The implementation passes acceptance, but still takes too many clicks.",
            "recommended_action": "Add a faster path.",
            "suggested_task_title": "Add fast path",
            "suggested_task_summary": "Reduce the number of steps for frequent users.",
        }
    )
    reviewed = json.loads(
        _run_cli(
            root,
            "--json",
            "task",
            "review",
            task_id,
            "--checkpoint",
            "manual",
            "--provider",
            "manual",
            "--summary",
            "Value gap remains.",
            "--recommendation",
            "proceed_with_followups",
            "--finding-json",
            finding,
        ).stdout
    )

    finding_id = reviewed["findings"][0]["finding_id"]
    followup = json.loads(
        _run_cli(
            root,
            "--json",
            "task",
            "create-from-finding",
            finding_id,
        ).stdout
    )
    listed = json.loads(
        _run_cli(
            root,
            "--json",
            "review",
            "list",
            "--task-id",
            task_id,
            "--include-findings",
        ).stdout
    )

    assert reviewed["review"]["overall_recommendation"] == "proceed_with_followups"
    assert followup["task"]["source_finding_id"] == finding_id
    assert listed["findings"][0]["followup_task_id"] == followup["task"]["task_id"]
