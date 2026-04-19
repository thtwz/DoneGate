from __future__ import annotations

from collections import Counter

from delivery_mcp.domain.lifecycle import needs_docs, needs_verification, next_action_rank, normalize_task
from delivery_mcp.models import DashboardSummary, Task, TaskStatus


def _task_brief(task: Task) -> dict[str, str | None | bool]:
    return {
        "task_id": task.task_id,
        "title": task.title,
        "status": task.status.value,
        "blocked_reason": task.blocked_reason,
        "needs_revalidation": task.needs_revalidation,
        "stale_reason": task.stale_reason,
    }


def build_dashboard(project_name: str, tasks: list[Task], limit: int = 10) -> DashboardSummary:
    tasks = [normalize_task(task) for task in tasks]
    counts = Counter(task.status.value for task in tasks)
    blocked = [_task_brief(task) for task in tasks if task.status == TaskStatus.BLOCKED]
    missing_verification = [_task_brief(task) for task in tasks if needs_verification(task)]
    missing_docs = [_task_brief(task) for task in tasks if needs_docs(task)]

    def priority(task: Task) -> tuple[int, str]:
        return (next_action_rank(task), task.task_id)

    next_actions = [_task_brief(task) for task in sorted(tasks, key=priority)[:limit] if priority(task)[0] < 9]
    return DashboardSummary(project_name=project_name, total_tasks=len(tasks), counts_by_status=dict(sorted(counts.items())), blocked_tasks=blocked, missing_verification=missing_verification, missing_docs=missing_docs, next_actions=next_actions)
