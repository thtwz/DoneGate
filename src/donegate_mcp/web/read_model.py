"""Non-mutating projections for the browser. Never instantiate write stores."""
from __future__ import annotations

from collections import Counter
from contextlib import contextmanager
import difflib
import json
from pathlib import Path
from typing import Any

from donegate_mcp.domain.evidence import input_snapshot
from donegate_mcp.errors import DoneGateMcpError
from donegate_mcp.models import Task, VerificationStatus, WorkflowIntent, utc_now
from donegate_mcp.storage.fs import read_json
from donegate_mcp.storage.spec_store import SpecStore
from donegate_mcp.storage.workspace_lock import fcntl
from donegate_mcp.web.registry import ProjectRegistry, validate_entry


@contextmanager
def project_read_lock(data: Path):
    # Current DoneGate initialization creates this file. Legacy stores without it
    # remain readable without creating directories as a side effect of viewing.
    path = data / "locks" / "write.lock"
    if not path.exists():
        yield
        return
    with path.open("rb") as handle:
        if fcntl is not None:
            fcntl.flock(handle.fileno(), fcntl.LOCK_SH)
        try:
            yield
        finally:
            if fcntl is not None:
                fcntl.flock(handle.fileno(), fcntl.LOCK_UN)


def jsonl_rows(path: Path, warnings: list[str]) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    rows = []
    for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if not line.strip():
            continue
        try:
            row = json.loads(line)
            if not isinstance(row, dict):
                raise ValueError("expected object")
            if "payload" in row and not isinstance(row["payload"], dict):
                raise ValueError("expected event payload object")
            rows.append(row)
        except ValueError:
            warnings.append(f"历史记录无法读取：{path.name} 第 {number} 行")
    return rows


def _changes(data: Path, tasks: list[dict[str, Any]], warnings: list[str]) -> list[dict[str, Any]]:
    changes = []
    revisions = SpecStore(data).list()
    known = {row["id"]: row for row in revisions}
    previous: dict[str, dict[str, Any]] = {}
    for row in sorted(revisions, key=lambda r: (r["spec_ref"], r["version"])):
        old = previous.get(row["spec_ref"])
        changes.append({
            "id": row["id"], "kind": "snapshot", "spec_ref": row["spec_ref"],
            "timestamp": row["timestamp"], "reason": row["reason"], "version": row["version"],
            "previous_version": old["version"] if old else None,
            "previous_hash": row["previous_hash"], "current_hash": row["spec_hash"],
            "affected_task_ids": row["affected_task_ids"], "history_available": old is not None,
            "content": row["content"],
            "diff": "".join(line if line.endswith("\n") else line + "\n\\ No newline at end of file\n"
                for line in difflib.unified_diff(old["content"].splitlines(keepends=True),
                row["content"].splitlines(keepends=True), fromfile=f"v{old['version']}",
                tofile=f"v{row['version']}")) if old else None,
        })
        previous[row["spec_ref"]] = row
    for task in tasks:
        for index, event in enumerate(task["events"]):
            if event.get("type") != "spec_drift_detected":
                continue
            payload = event.get("payload", {})
            revision = known.get(payload.get("revision_id"))
            if revision and task["task_id"] in revision["affected_task_ids"]:
                continue
            changes.append({"id": f"{task['task_id']}:{index}", "kind": "spec_drift",
                "spec_ref": payload.get("spec_ref", task["spec_ref"]), "timestamp": event.get("timestamp", ""),
                "reason": payload.get("reason", "需求发生变化"), "version": None, "previous_version": None,
                "previous_hash": None, "current_hash": payload.get("spec_hash"),
                "affected_task_ids": [task["task_id"]], "diff": None, "history_available": False})
    for index, row in enumerate(jsonl_rows(data / "deviations.jsonl", warnings)):
        changes.append({"id": f"deviation:{index}", "kind": "deviation", "spec_ref": row.get("spec_ref", ""),
            "timestamp": row.get("timestamp", ""), "reason": row.get("summary", ""), "content": row.get("details", ""),
            "version": None, "previous_version": None, "previous_hash": None, "current_hash": None,
            "affected_task_ids": [row["task_id"]] if row.get("task_id") else [], "diff": None, "history_available": False})
    return sorted(changes, key=lambda row: (row["timestamp"], row["id"]), reverse=True)


def project_detail(entry: dict[str, Any], *, include_history: bool = True) -> dict[str, Any]:
    entry = validate_entry(entry)
    data, repo = Path(entry["data_root"]), Path(entry["repo_root"])
    warnings: list[str] = []
    with project_read_lock(data):
        entry = validate_entry(entry)
        tasks = []
        for path in sorted((data / "tasks").glob("*.json")):
            task = Task.from_dict(read_json(path))
            stale = task.verification_status == VerificationStatus.PASSED and input_snapshot(task, repo, data) != task.verification_input_hash
            if stale:
                # Match service freshness semantics on an in-memory task only.
                task.verification_status = VerificationStatus.UNKNOWN
                task.verified_at = task.done_at = None
                task.workflow_intent = WorkflowIntent.AWAITING_VERIFICATION
            row = task.to_dict()
            row["evidence_stale"] = stale
            row["events"] = jsonl_rows(data / "events" / f"{path.stem}.jsonl", warnings) if include_history else []
            tasks.append(row)
        counts = Counter(task["status"] for task in tasks)
        summary = {"total_tasks": len(tasks), "done_tasks": counts["done"],
            "completion_rate": round(counts["done"] / len(tasks) * 100, 1) if tasks else None,
            "counts_by_status": dict(counts), "needs_revalidation": sum(bool(t["needs_revalidation"]) for t in tasks),
            "blocked_tasks": counts["blocked"]}
        changes = _changes(data, tasks, warnings) if include_history else []
    return {"project": entry, "summary": summary, "tasks": tasks, "changes": changes,
            "updated_at": utc_now(), "warnings": warnings}


def portfolio(registry: ProjectRegistry) -> dict[str, Any]:
    rows = []
    for entry in registry.list():
        try:
            detail = project_detail(entry, include_history=False)
            rows.append({**detail["project"], "summary": detail["summary"], "error": None, "updated_at": detail["updated_at"]})
        except (DoneGateMcpError, OSError, ValueError, KeyError, TypeError) as exc:
            rows.append({**entry, "error": str(exc), "summary": None, "updated_at": None})
    return {"projects": rows}
