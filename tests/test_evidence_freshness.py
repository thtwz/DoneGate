from __future__ import annotations

import subprocess

import pytest

from donegate_mcp.domain.services import DoneGateService
from donegate_mcp.errors import TransitionError, ValidationError


def setup_task(tmp_path, **kwargs):
    subprocess.run(['git', 'init', '-q', str(tmp_path)], check=True)
    (tmp_path / 'feature.py').write_text('value = 1\n')
    (tmp_path / 'spec.md').write_text('Deliver feature\n')
    service = DoneGateService(tmp_path / '.donegate-mcp')
    service.init_project('demo', repo_root=tmp_path)
    task_id = service.create_task('feature', 'spec.md', **kwargs)['task']['task_id']
    service.activate_task(task_id, repo_root=tmp_path)
    service.transition_task(task_id, 'in_progress')
    return service, task_id


@pytest.mark.parametrize('change', ['source', 'spec', 'new_file', 'delete', 'protocol'])
def test_changed_inputs_invalidate_passed_evidence_before_done(tmp_path, change):
    service, task_id = setup_task(tmp_path)
    service.record_verification(task_id, 'passed')
    service.record_doc_sync(task_id, 'synced')
    if change == 'source':
        (tmp_path / 'feature.py').write_text('value = broken\n')
    elif change == 'spec':
        (tmp_path / 'spec.md').write_text('New requirement\n')
    elif change == 'new_file':
        (tmp_path / 'new.py').write_text('new code\n')
    elif change == 'delete':
        (tmp_path / 'feature.py').unlink()
    else:
        service.update_acceptance_protocol(task_id, test_commands=['false'])
    with pytest.raises(TransitionError, match='verification'):
        service.transition_task(task_id, 'done')
    supervision = service.get_supervision(repo_root=tmp_path)['supervision']
    assert supervision['status'] == 'stale_verification'
    assert supervision['active_task']['verification_status'] != 'passed'


def test_scoped_evidence_survives_unrelated_files_and_generated_artifacts(tmp_path):
    service, task_id = setup_task(tmp_path, owned_paths=['feature.py'], required_artifacts=['report.txt'])
    service.record_verification(task_id, 'passed')
    (tmp_path / 'unrelated.txt').write_text('Other task\n')
    (tmp_path / 'report.txt').write_text('Generated evidence\n')
    service.record_doc_sync(task_id, 'synced', notes='No documentation change needed')
    assert service.transition_task(task_id, 'done')['task']['status'] == 'done'


def test_self_test_uses_project_workdir_and_detects_changes_during_execution(tmp_path, monkeypatch):
    service, task_id = setup_task(tmp_path, test_commands=["printf 'value = 2\\n' > feature.py"])
    monkeypatch.chdir(tmp_path.parent)
    result = service.run_self_test(task_id)
    assert (tmp_path / 'feature.py').read_text() == 'value = 2\n'
    assert result['task']['verification_status'] == 'failed'
    assert result['exit_code'] != 0
    assert 'changed' in result['record']['notes']


def test_self_test_rejects_another_project_workdir(tmp_path):
    service, task_id = setup_task(tmp_path, test_commands=['true'])
    with pytest.raises(ValidationError, match='workdir'):
        service.run_self_test(task_id, workdir=str(tmp_path.parent))


def test_unchanged_completed_review_is_reused_at_done(tmp_path):
    service, task_id = setup_task(tmp_path)
    service.transition_task(task_id, 'awaiting_verification')
    service.record_task_review(task_id, checkpoint='submit', provider_id='host_skill', summary='User outcome checked')
    service.record_verification(task_id, 'passed')
    service.record_doc_sync(task_id, 'synced')
    service.transition_task(task_id, 'done')
    reviews = service.list_reviews(task_id=task_id)['reviews']
    assert len(reviews) == 1
    assert reviews[0]['status'] == 'completed'


def test_changed_inputs_request_new_advisory_without_blocking_done(tmp_path):
    service, task_id = setup_task(tmp_path)
    service.transition_task(task_id, 'awaiting_verification')
    service.record_task_review(task_id, checkpoint='submit', provider_id='host_skill', summary='Checked first version')
    (tmp_path / 'feature.py').write_text('value = 2\n')
    service.record_verification(task_id, 'passed')
    service.record_doc_sync(task_id, 'synced')
    assert service.transition_task(task_id, 'done')['task']['status'] == 'done'
    assert len(service.list_reviews(task_id=task_id, status='requested')['reviews']) == 1


def test_gate_reuses_current_manual_evidence_without_forcing_self_test(tmp_path):
    service, task_id = setup_task(tmp_path)
    service.record_verification(task_id, 'passed', ref='manual-observation')
    result = service.ensure_verification(task_id)
    assert result['reused'] is True
    assert result['task']['last_verification_ref'] == 'manual-observation'
    (tmp_path / 'feature.py').write_text('changed\n')
    with pytest.raises(ValidationError, match='manual'):
        service.ensure_verification(task_id)


def test_staging_identical_content_preserves_verification(tmp_path):
    service, task_id = setup_task(tmp_path)
    service.record_verification(task_id, 'passed')
    subprocess.run(['git', '-C', str(tmp_path), 'add', 'feature.py', 'spec.md'], check=True)
    service.record_doc_sync(task_id, 'synced')
    assert service.transition_task(task_id, 'done')['task']['status'] == 'done'


def test_repository_root_scope_includes_source_changes(tmp_path):
    service, task_id = setup_task(tmp_path, owned_paths=['.'])
    service.record_verification(task_id, 'passed')
    service.record_doc_sync(task_id, 'synced')
    (tmp_path / 'feature.py').write_text('broken\n')
    with pytest.raises(TransitionError, match='verification'):
        service.transition_task(task_id, 'done')


def test_self_test_never_binds_a_new_snapshot_after_running(tmp_path, monkeypatch):
    service, task_id = setup_task(tmp_path, test_commands=['true'])
    record = service.record_verification
    def change_then_record(*args, **kwargs):
        (tmp_path / 'feature.py').write_text('untested\n')
        return record(*args, **kwargs)
    monkeypatch.setattr(service, 'record_verification', change_then_record)
    result = service.run_self_test(task_id)
    assert result['task']['verification_status'] == 'failed'
    assert result['exit_code'] != 0


def test_losing_git_metadata_does_not_downgrade_bound_evidence_to_manual(tmp_path):
    service, task_id = setup_task(tmp_path)
    service.record_verification(task_id, 'passed')
    service.record_doc_sync(task_id, 'synced')
    (tmp_path / '.git').rename(tmp_path / 'old-git')
    with pytest.raises(TransitionError, match='verification'):
        service.transition_task(task_id, 'done')


def test_completing_an_old_review_does_not_claim_new_inputs_were_reviewed(tmp_path):
    service, task_id = setup_task(tmp_path)
    service.transition_task(task_id, 'awaiting_verification')
    requested = service.list_reviews(task_id=task_id)['reviews'][0]
    (tmp_path / 'feature.py').write_text('new version\n')
    reviewed = service.record_task_review(task_id, checkpoint='submit', provider_id='host_skill', review_run_id=requested['review_run_id'], summary='Reviewed original version')['review']
    assert reviewed['source_input_hash'] == requested['source_input_hash']
    service.record_verification(task_id, 'passed')
    service.record_doc_sync(task_id, 'synced')
    service.transition_task(task_id, 'done')
    assert len(service.list_reviews(task_id=task_id, status='requested')['reviews']) == 1


@pytest.mark.parametrize('hook_name', ['pre-commit.sh', 'pre-push.sh'])
def test_git_hooks_reject_a_failed_configured_check(tmp_path, hook_name):
    import os
    from pathlib import Path
    service, task_id = setup_task(tmp_path, test_commands=['false'])
    subprocess.run(['git', '-C', str(tmp_path), 'add', 'feature.py', 'spec.md'], check=True)
    subprocess.run(['git', '-C', str(tmp_path), '-c', 'user.name=Test', '-c', 'user.email=test@example.com', 'commit', '-qm', 'fixture'], check=True)
    root = Path(__file__).resolve().parents[1]
    env = {key: value for key, value in os.environ.items() if not key.startswith('DONEGATE_MCP_') and key != 'TASK_ID'}
    env['PYTHONPATH'] = str(root / 'src')
    result = subprocess.run([str(root / 'scripts' / hook_name)], cwd=tmp_path, env=env, capture_output=True, text=True)
    assert result.returncode != 0
    assert service.tasks.load(task_id).verification_status.value == 'failed'
