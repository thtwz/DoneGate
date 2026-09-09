from __future__ import annotations

import json
from typing import Any


def _batch_summary(batch: dict[str, Any]) -> str:
    return f"{batch['batch_id']} {batch.get('selected_mode', 'auto')} {len(batch.get('task_ids', []))} tasks {batch.get('title', '')}"


def render(payload: dict[str, Any], as_json: bool) -> str:
    if as_json:
        return json.dumps(payload, indent=2, sort_keys=True)
    if "created_count" in payload:
        lines = [f"created={payload['created_count']}"]
        for index, task in enumerate(payload.get("tasks", []), start=1):
            label = task.get("task_id", f"item {index}")
            lines.append(f"{label} {task.get('status', 'failed')} {task.get('title', '')}".rstrip())
            if task.get("errors"):
                lines.append("ERROR: " + "; ".join(task["errors"]))
        if not payload.get("ok", False) and payload.get("errors"):
            lines.append("ERROR: " + "; ".join(payload["errors"]))
        return "\n".join(lines)
    if "batch" in payload or "active_batch" in payload:
        batch = payload.get("batch") or payload.get("active_batch")
        lines = [_batch_summary(batch) if batch else "no active batch"]
        if "executed_count" in payload:
            lines.append(f"executed={payload['executed_count']} reused={payload.get('reused_count', 0)}")
        for task in payload.get("tasks", []):
            result = "ok" if task.get("ok") else "failed"
            lines.append(f"{task['task_id']} {result}" + (": " + "; ".join(task["errors"]) if task.get("errors") else ""))
        if not payload.get("ok", False):
            lines.append("ERROR: " + "; ".join(payload.get("errors", ["unknown error"])))
        return "\n".join(lines)
    if not payload.get("ok", False):
        return "ERROR: " + "; ".join(payload.get("errors", ["unknown error"]))
    if "batches" in payload:
        return "\n".join(_batch_summary(batch) for batch in payload["batches"]) or "no batches"
    if "context" in payload:
        context = payload["context"]
        active = context.get("active_task")
        task = f"{active['task_id']} {active['status']}" if active else "no active task"
        if context.get("active_batch"):
            task = _batch_summary(context["active_batch"])
        return f"{context['repo_root']} [{context.get('branch') or 'detached'}]: {task}\n{context['status']}: {context['next_action']}"
    if "review" in payload:
        review = payload["review"]
        return f"{review['review_run_id']} {review['status']} {review['checkpoint']}"
    if "finding" in payload and "task" not in payload:
        finding = payload["finding"]
        return f"{finding['finding_id']} {finding['disposition']} {finding['title']}"
    if "reviews" in payload:
        return "\n".join(f"{review['review_run_id']} {review['status']} {review['checkpoint']} {review['task_id']}" for review in payload["reviews"]) or "no reviews"
    if "task" in payload:
        task = payload["task"]
        return f"{task['task_id']} {task['status']} {task['title']}"
    if "dashboard" in payload:
        dashboard = payload["dashboard"]
        return f"{dashboard['project_name']}: {dashboard['total_tasks']} tasks"
    if "supervision" in payload:
        supervision = payload["supervision"]
        return f"{supervision['status']}: {len(supervision['changed_files'])} changed files"
    if "onboarding" in payload:
        onboarding = payload["onboarding"]
        branch = onboarding.get("branch") or "detached"
        return f"{onboarding['agent']} onboarding for {branch}"
    if "tasks" in payload:
        return "\n".join(f"{task['task_id']} {task['status']} {task['title']}" for task in payload["tasks"]) or "no tasks"
    if "project" in payload:
        project = payload["project"]
        return f"initialized {project['project_name']}"
    if "active_task" in payload:
        task = payload["active_task"]
        if task is None:
            return "no active task"
        return f"active {task['task_id']} {task['status']} {task['title']}"
    return "ok"
