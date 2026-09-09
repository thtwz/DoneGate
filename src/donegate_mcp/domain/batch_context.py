"""Branch-bound batch supervision; never execute checks during context reads."""
from dataclasses import replace

from donegate_mcp.models import utc_now


def batch_supervision(service, repo, changed_files):
    from donegate_mcp.domain.batches import BatchService, batch_evidence_reader
    batch = BatchService(service).active().get('batch')
    if not batch:
        return None
    tasks = [service.tasks.load(task_id) for task_id in batch['task_ids']]
    reader = batch_evidence_reader(repo, service.data_root)
    current = {task.task_id: reader.current(task) for task in tasks}
    for task in tasks:
        service._invalidate_stale_verification(task, lambda item: current[item.task_id])
    scope = [] if any(not t.owned_paths for t in tasks) else sorted({p for t in tasks for p in t.owned_paths})
    covered, uncovered = service._classify_changed_files(changed_files, replace(tasks[0], owned_paths=scope))
    if uncovered:
        status = 'task_mismatch'
    elif any(t.blocked_reason or t.needs_revalidation for t in tasks):
        status = 'needs_revalidation'
    elif any(t.verification_status.value != 'passed' for t in tasks):
        status = 'stale_verification'
    elif any(t.doc_sync_status.value != 'synced' for t in tasks):
        status = 'stale_docs'
    else:
        status = 'tracked' if changed_files else 'clean'
    return {'schema_version': 1, 'updated_at': utc_now(), 'repo_root': str(repo),
            'status': status, 'changed_files': changed_files, 'covered_files': covered,
            'uncovered_files': uncovered, 'active_task_id': None, 'active_task': None,
            'active_batch': batch, 'active_batch_id': batch['batch_id'],
            'advisory_summary': {}, 'policy': service._supervision_policy(status)}
