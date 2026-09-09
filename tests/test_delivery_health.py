import pytest

from donegate_mcp.errors import TransitionError
from test_evidence_freshness import setup_task


def test_source_drift_preserves_delivery_but_cannot_pass_current_gate(tmp_path):
    service, task_id = setup_task(tmp_path)
    service.record_verification(task_id, 'passed')
    service.record_doc_sync(task_id, 'synced')
    closed = service.transition_task(task_id, 'done')['task']
    (tmp_path / 'feature.py').write_text('changed = True\n')
    current = service.get_task(task_id)['task']
    assert current['status'] == 'done'
    assert current['done_at'] == closed['done_at']
    assert current['evidence_stale'] is True
    assert current['verification_health'] == 'stale'
    with pytest.raises(TransitionError, match='verification'):
        service.transition_task(task_id, 'done')
    context = service.get_context(repo_root=tmp_path)['context']
    assert context['blockers']
    service.record_verification(task_id, 'failed', ref='observed failing regression')
    assert service.get_task(task_id)['task']['done_at'] == closed['done_at']
    service.record_verification(task_id, 'passed', ref='new acceptance')
    assert service.transition_task(task_id, 'done')['task']['done_at'] == closed['done_at']


def test_explicit_requirement_change_reopens_delivery(tmp_path):
    service, task_id = setup_task(tmp_path)
    service.record_verification(task_id, 'passed')
    service.record_doc_sync(task_id, 'synced')
    service.transition_task(task_id, 'done')
    (tmp_path / 'spec.md').write_text('Different requested behavior')
    service.refresh_spec(str(tmp_path / 'spec.md'), reason='User changed requirement')
    current = service.get_task(task_id)['task']
    assert current['done_at'] is None
    assert current['needs_revalidation']
