"""Shared small transport presentation; full domain payloads remain available."""
from __future__ import annotations

from typing import Any

_TASK_FIELDS = {
    'task_id', 'title', 'status', 'projected_status', 'workflow_intent', 'owned_paths',
    'verification_status', 'doc_sync_status', 'needs_revalidation', 'blocked_reason',
    'last_verification_ref', 'last_doc_sync_ref', 'advisory_summary',
}


def compact_payload(value: Any) -> Any:
    if isinstance(value, list):
        return [compact_payload(item) for item in value]
    if not isinstance(value, dict):
        return value
    if 'task_id' in value and 'verification_status' in value:
        value = {key: item for key, item in value.items() if key in _TASK_FIELDS}
    if 'exit_code' in value and 'ref' in value:
        value = {key: item for key, item in value.items() if key not in {'commands', 'stdout', 'stderr'}}
    return {key: compact_payload(item) for key, item in value.items() if item is not None}
