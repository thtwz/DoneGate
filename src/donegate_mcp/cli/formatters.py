from __future__ import annotations

import json
from typing import Any


def render(payload: dict[str, Any], as_json: bool) -> str:
    if as_json:
        return json.dumps(payload, indent=2, sort_keys=True)
    if not payload.get("ok", False):
        return "ERROR: " + "; ".join(payload.get("errors", ["unknown error"]))
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
