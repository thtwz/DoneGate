from __future__ import annotations

from collections import Counter

from donegate_mcp.domain.lifecycle import needs_docs, needs_verification, next_action_rank, normalize_task
from typing import Any

from donegate_mcp.models import DashboardSummary, Task, TaskStatus


def _task_brief(task: Task, advisory_summary: dict[str, Any] | None = None) -> dict[str, str | None | bool | int]:
    payload: dict[str, str | None | bool | int] = {
        "task_id": task.task_id,
        "title": task.title,
        "status": task.status.value,
        "blocked_reason": task.blocked_reason,
        "needs_revalidation": task.needs_revalidation,
        "stale_reason": task.stale_reason,
    }
    if advisory_summary is not None:
        payload["open_advisories"] = int(advisory_summary.get("open_advisories", 0))
        payload["high_severity_advisories"] = int(advisory_summary.get("high_severity_advisories", 0))
        payload["followup_spawned_advisories"] = int(advisory_summary.get("followup_spawned_advisories", 0))
        payload["pending_reviews"] = int(advisory_summary.get("pending_reviews", 0))
    return payload


def build_dashboard(project_name: str, tasks: list[Task], advisory_summaries: dict[str, dict[str, Any]] | None = None, limit: int = 10) -> DashboardSummary:
    tasks = [normalize_task(task) for task in tasks]
    advisory_summaries = advisory_summaries or {}
    counts = Counter(task.status.value for task in tasks)
    blocked = [_task_brief(task, advisory_summaries.get(task.task_id)) for task in tasks if task.status == TaskStatus.BLOCKED]
    missing_verification = [_task_brief(task, advisory_summaries.get(task.task_id)) for task in tasks if needs_verification(task)]
    missing_docs = [_task_brief(task, advisory_summaries.get(task.task_id)) for task in tasks if needs_docs(task)]

    def priority(task: Task) -> tuple[int, str]:
        return (next_action_rank(task), task.task_id)

    next_actions = [_task_brief(task, advisory_summaries.get(task.task_id)) for task in sorted(tasks, key=priority)[:limit] if priority(task)[0] < 9]
    tasks_with_open_advisories = [
        _task_brief(task, advisory_summaries.get(task.task_id))
        for task in tasks
        if int((advisory_summaries.get(task.task_id) or {}).get("open_advisories", 0)) > 0
    ]
    tasks_with_pending_reviews = [
        _task_brief(task, advisory_summaries.get(task.task_id))
        for task in tasks
        if int((advisory_summaries.get(task.task_id) or {}).get("pending_reviews", 0)) > 0
    ]
    open_advisories = sum(int(summary.get("open_advisories", 0)) for summary in advisory_summaries.values())
    high_severity_advisories = sum(int(summary.get("high_severity_advisories", 0)) for summary in advisory_summaries.values())
    followup_spawned_advisories = sum(int(summary.get("followup_spawned_advisories", 0)) for summary in advisory_summaries.values())
    pending_advisory_reviews = sum(int(summary.get("pending_reviews", 0)) for summary in advisory_summaries.values())
    return DashboardSummary(
        project_name=project_name,
        total_tasks=len(tasks),
        counts_by_status=dict(sorted(counts.items())),
        blocked_tasks=blocked,
        missing_verification=missing_verification,
        missing_docs=missing_docs,
        next_actions=next_actions,
        open_advisories=open_advisories,
        high_severity_advisories=high_severity_advisories,
        followup_spawned_advisories=followup_spawned_advisories,
        pending_advisory_reviews=pending_advisory_reviews,
        tasks_with_open_advisories=tasks_with_open_advisories,
        tasks_with_pending_reviews=tasks_with_pending_reviews,
    )
