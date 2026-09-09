"""Real Git workspaces exercise explicit batch coverage and durable reuse."""
import json
import subprocess
from pathlib import Path

import pytest

from donegate_mcp.domain.services import DoneGateService
from donegate_mcp.errors import ValidationError


@pytest.fixture
def setup(tmp_path):
    repo = tmp_path / 'repo'
    repo.mkdir()
    subprocess.run(['git', 'init', '-q', str(repo)], check=True)
    (repo / 'spec.md').write_text('requirements')
    (repo / 'a.py').write_text('a')
    (repo / 'b.py').write_text('b')
    service = DoneGateService(repo / '.donegate-mcp', repo)
    service.init_project('batch test', repo_root=repo)
    from donegate_mcp.domain.batches import BatchService
    batches = BatchService(service)
    def task(scope='a.py', command='true', mode='self-test'):
        return service.create_task('task', 'spec.md', verification_mode=mode,
                                   test_commands=[command] if command else [], owned_paths=[scope] if scope else [])['task']['task_id']
    return repo, service, batches, task


def test_shared_command_durable_reuse_and_force(setup):
    repo, service, batches, task = setup
    command = 'echo ran >> .donegate-mcp/counter'
    ids = [task('a.py', command), task('b.py', command)]
    batch = batches.create('shared', ids)['batch']
    assert batch['selected_mode'] == 'batch'
    first = batches.run(batch['batch_id'])
    assert first['ok'] and first['executed_count'] == 1
    assert (service.data_root / 'counter').read_text().splitlines() == ['ran']
    from donegate_mcp.domain.batches import BatchService
    second = BatchService(service).run(batch['batch_id'])
    assert second['ok'] and second['executed_count'] == 0 and second['reused_count'] == 1
    assert batches.run(batch['batch_id'], force=True)['executed_count'] == 1
    assert len(list((service.data_root / 'batch-runs').glob('*.json'))) == 3


def test_scope_and_dependency_changes(setup):
    repo, service, batches, task = setup
    a, b = task('a.py', 'echo a'), task('b.py', 'echo b')
    batch = batches.create('independent', [a, b])['batch']['batch_id']
    assert batches.run(batch)['ok']
    (repo / 'a.py').write_text('changed')
    changed = batches.run(batch)
    assert changed['executed_count'] == 1 and changed['reused_count'] == 1
    dependent = batches.create('dependent', [a, b], dependencies={b: [a]})['batch']['batch_id']
    assert batches.run(dependent)['ok']
    (repo / 'a.py').write_text('changed again')
    assert batches.run(dependent)['executed_count'] == 2


def test_failures_keep_independent_success_and_missing_coverage_blocks(setup):
    _, service, batches, task = setup
    good, bad, missing = task(command='true'), task('b.py', 'false'), task(command=None)
    result = batches.run(batches.create('mixed', [bad, good, missing])['batch']['batch_id'])
    assert not result['ok']
    outcomes = {row['task_id']: row for row in result['tasks']}
    assert outcomes[good]['ok'] and not outcomes[bad]['ok'] and not outcomes[missing]['ok']
    assert service.tasks.load(good).verification_status.value == 'passed'


def test_manual_acceptance_is_not_fabricated(setup):
    _, service, batches, task = setup
    manual = task(command='true', mode='manual')
    batch = batches.create('manual', [manual])['batch']['batch_id']
    assert not batches.run(batch)['ok']
    service.record_verification(manual, 'passed', notes='observed acceptance')
    assert batches.run(batch)['ok']


def test_invalid_graph_and_duplicate_members_do_not_write(setup):
    _, service, batches, task = setup
    a, b = task(), task('b.py')
    for ids, deps in [([a, a], None), ([a, 'TASK-9999'], None), ([a, b], {a: [b], b: [a]}), ([a], {b: [a]})]:
        with pytest.raises(ValidationError):
            batches.create('bad', ids, dependencies=deps)
    assert batches.list()['batches'] == []


def test_missing_logs_disable_cache_and_current_evidence(setup):
    _, service, batches, task = setup
    tid = task()
    batch = batches.create('logs', [tid])['batch']['batch_id']
    result = batches.run(batch)
    Path(result['checks'][0]['stdout_path']).unlink()
    assert not batches.evidence_current(service.tasks.load(tid))
    assert batches.run(batch)['executed_count'] == 1


def test_inputs_changed_by_command_never_pass(setup):
    _, service, batches, task = setup
    tid = task(command='echo changed >> a.py')
    result = batches.run(batches.create('drift', [tid])['batch']['batch_id'])
    assert not result['ok']
    assert service.tasks.load(tid).verification_status.value != 'passed'


def test_single_mode_does_not_share_between_tasks(setup):
    _, _, batches, task = setup
    a, b = task(), task('b.py')
    result = batches.run(batches.create('isolated', [a, b], mode='single', rationale='Isolate task checks')['batch']['batch_id'])
    assert result['executed_count'] == 2
    assert batches.create('risk', [a, b], risk='high')['batch']['selected_mode'] == 'single'


def test_unknown_scope_is_conservative(setup):
    repo, _, batches, task = setup
    tid = task('does-not-exist')
    batch = batches.create('unknown scope', [tid])['batch']['batch_id']
    assert batches.run(batch)['ok']
    (repo / 'b.py').write_text('outside unknown scope')
    assert batches.run(batch)['executed_count'] == 1


def test_external_dependency_requires_current_pass(setup):
    repo, service, batches, task = setup
    dep, member = task(), task('b.py')
    batch = batches.create('external', [member], dependencies={member: [dep]})['batch']['batch_id']
    assert not batches.run(batch)['ok']
    service.run_self_test(dep)
    assert batches.run(batch)['ok']
    (repo / 'a.py').write_text('changed')
    assert not batches.run(batch)['ok']


def test_bulk_validates_before_writes_and_activation_is_branch_bound(setup):
    repo, service, batches, task = setup
    with pytest.raises(ValidationError):
        batches.create_tasks([{'title': 'valid', 'spec_ref': 'spec.md'}, {'title': 'invalid'}])
    assert not service.tasks.list()
    result = batches.create_tasks([{'title': 'valid', 'spec_ref': 'spec.md'}])
    tid = result['tasks'][0]['task_id']
    batch = batches.create('active', [tid])['batch']['batch_id']
    batches.activate(batch)
    assert batches.active()['batch']['batch_id'] == batch
    subprocess.run(['git', '-C', str(repo), 'symbolic-ref', 'HEAD', 'refs/heads/other'], check=True)
    assert batches.active()['batch'] is None


def test_later_command_invalidates_previously_passed_and_reused_checks(setup):
    _, service, batches, task = setup
    a, b = task('a.py', 'true'), task('b.py', 'echo later >> a.py')
    batch = batches.create('late mutation', [a, b])['batch']['batch_id']
    result = batches.run(batch)
    assert not result['ok']
    assert not next(row for row in result['tasks'] if row['task_id'] == a)['ok']
    assert service.tasks.load(a).verification_status.value != 'passed'


def test_manual_batch_failure_invalidates_present_task_gate(setup):
    _, service, batches, task = setup
    tid = task(command='false', mode='manual')
    service.record_verification(tid, 'passed', notes='manual acceptance observed')
    result = batches.run(batches.create('manual failed check', [tid])['batch']['batch_id'])
    assert not result['ok']
    assert not batches._passed(service.tasks.load(tid))


def test_manual_only_durable_batch_rerun(setup):
    _, service, batches, task = setup
    tid = task(command=None, mode='manual')
    service.record_verification(tid, 'passed', notes='manual acceptance observed')
    bid = batches.create('manual only', [tid])['batch']['batch_id']
    assert batches.run(bid)['ok']
    assert batches.run(bid)['ok']


def test_environment_and_protocol_changes_invalidate(setup, monkeypatch):
    _, service, batches, task = setup
    tid = task()
    bid = batches.create('environment', [tid])['batch']['batch_id']
    assert batches.run(bid)['ok']
    monkeypatch.setenv('BATCH_TEST_SETTING', 'new')
    assert batches.evidence_current(service.tasks.load(tid))  # Dashboard uses recorded execution environment.
    assert batches.run(bid)['executed_count'] == 1
    service.update_acceptance_protocol(tid, test_commands=['echo new'])
    assert batches.run(bid)['executed_count'] == 1


def test_transition_validation_is_all_or_nothing(setup):
    _, service, batches, task = setup
    a, b = task(), task('b.py')
    service.transition_task(a, 'ready')
    service.block_task(b, 'blocked')
    result = batches.transition(batches.create('transition', [a, b])['batch']['batch_id'], 'in_progress')
    assert not result['ok']
    assert service.tasks.load(a).status.value == 'ready'


def test_batch_evidence_dependency_staleness_survives_outside_run(setup):
    repo, service, batches, task = setup
    a, b = task(), task('b.py', 'echo b')
    bid = batches.create('dependencies', [a, b], dependencies={b: [a]})['batch']['batch_id']
    assert batches.run(bid)['ok']
    (repo / 'a.py').write_text('new dependency')
    from donegate_mcp.domain.batches import evidence_current_read
    assert not evidence_current_read(service.tasks.load(b), repo, service.data_root)


def test_bound_member_cannot_replace_dependency_evidence_with_standalone_pass(setup):
    repo, service, batches, task = setup
    a, b = task(), task('b.py')
    bid = batches.create('binding', [a, b], dependencies={b: [a]})['batch']['batch_id']
    assert batches.run(bid)['ok']
    (repo / 'a.py').write_text('changed')
    service.record_verification(b, 'passed', notes='standalone assertion')
    assert not batches.evidence_current(service.tasks.load(b))


def test_recording_race_returns_failure_and_immutable_failed_run(setup, monkeypatch):
    repo, service, batches, task = setup
    tid = task()
    bid = batches.create('record race', [tid])['batch']['batch_id']
    original = service.record_verification
    def changed_before_record(*args, **kwargs):
        (repo / 'a.py').write_text('changed during recording')
        return original(*args, **kwargs)
    monkeypatch.setattr(service, 'record_verification', changed_before_record)
    result = batches.run(bid)
    assert not result['ok']
    assert not json.loads((service.data_root / 'batch-runs' / f"{result['run_id']}.json").read_text())['ok']


def test_reassignment_prevents_old_batch_overwriting_evidence(setup):
    _, service, batches, task = setup
    tid = task()
    old = batches.create('old', [tid])['batch']['batch_id']
    assert batches.run(old)['ok']
    new = batches.create('new', [tid])['batch']['batch_id']
    with pytest.raises(ValidationError, match='newer batch'):
        batches.run(old)
    assert service.tasks.load(tid).batch_id == new
    assert batches.run(new)['ok']


def test_transitive_external_dependency_change_reruns_consumer(setup):
    repo, _, batches, task = setup
    (repo / 'c.py').write_text('c')
    a, b, c = task(), task('b.py', 'echo b'), task('c.py', 'echo c')
    first = batches.create('dependency chain', [a, b], dependencies={b: [a]})['batch']['batch_id']
    second = batches.create('consumer', [c], dependencies={c: [b]})['batch']['batch_id']
    assert batches.run(first)['ok']
    assert batches.run(second)['ok']
    (repo / 'a.py').write_text('changed transitive input')
    assert batches.run(first)['ok']
    result = batches.run(second)
    assert result['ok'] and result['executed_count'] == 1


def test_cross_batch_dependency_cycle_rejected_before_binding(setup):
    _, service, batches, task = setup
    a, b = task(), task('b.py')
    batches.create('first', [a], dependencies={a: [b]})
    with pytest.raises(ValidationError, match='cycle'):
        batches.create('cycle', [b], dependencies={b: [a]})
    assert service.tasks.load(b).batch_id is None


def test_manual_unknown_scope_and_dependency_drift_stale_durable_acceptance(setup):
    repo, service, batches, task = setup
    tid = task('unknown', command=None, mode='manual')
    bid = batches.create('manual conservative', [tid])['batch']['batch_id']
    service.record_verification(tid, 'passed', notes='manual acceptance observed')
    assert batches.run(bid)['ok']
    (repo / 'b.py').write_text('changed outside unknown scope')
    assert not batches.evidence_current(service.tasks.load(tid))


def test_shared_check_final_audit_runs_once_per_check(setup, monkeypatch):
    _, _, batches, task = setup
    tids = [task() for _ in range(5)]
    bid = batches.create('bounded audit', tids)['batch']['batch_id']
    calls = []
    original = batches.evidence.check_current
    def count(*args, **kwargs):
        calls.append(1)
        return original(*args, **kwargs)
    monkeypatch.setattr(batches.evidence, 'check_current', count)
    assert batches.run(bid)['ok']
    assert len(calls) == 2  # Once after commands, once after fact recording.


def test_read_projection_shares_snapshots_only_within_one_read(setup, monkeypatch):
    repo, service, batches, task = setup
    tids = [task() for _ in range(5)]
    bid = batches.create('shared projection', tids)['batch']['batch_id']
    assert batches.run(bid)['ok']
    from donegate_mcp.domain.batches import batch_evidence_reader
    reader = batch_evidence_reader(repo, service.data_root)
    calls = []
    original = reader.snapshot
    def count(member):
        calls.append(member.task_id)
        return original(member)
    monkeypatch.setattr(reader, 'snapshot', count)
    assert all(reader.current(service.tasks.load(tid)) for tid in tids)
    assert len(calls) == len(tids)
    (repo / 'a.py').write_text('new read inputs')
    fresh = batch_evidence_reader(repo, service.data_root)
    assert not any(fresh.current(service.tasks.load(tid)) for tid in tids)


def test_manual_fact_survives_status_reads_but_explicit_failure_revokes(setup):
    _, service, batches, task = setup
    tid = task(command='true', mode='manual')
    bid = batches.create('manual retained fact', [tid])['batch']['batch_id']
    service.record_verification(tid, 'passed', notes='manual acceptance observed')
    service.get_task(tid)
    service.get_context()
    assert batches.run(bid)['ok']
    service.record_verification(tid, 'failed', notes='acceptance revoked')
    assert not batches.run(bid)['ok']


def test_manual_fact_cannot_survive_input_change_before_first_batch_run(setup):
    repo, service, batches, task = setup
    tid = task('unknown', command=None, mode='manual')
    bid = batches.create('manual retained scope', [tid])['batch']['batch_id']
    service.record_verification(tid, 'passed', notes='manual acceptance observed')
    (repo / 'b.py').write_text('change after manual acceptance')
    service.get_task(tid)
    assert not batches.run(bid)['ok']
    service.record_verification(tid, 'passed', notes='acceptance repeated on new inputs')
    service.get_task(tid)
    assert batches.run(bid)['ok']


def test_live_environment_change_blocks_delivery_without_changing_read_health(setup, monkeypatch):
    _, service, batches, task = setup
    tid = task()
    bid = batches.create('live environment gate', [tid])['batch']['batch_id']
    assert batches.run(bid)['ok']
    batches.doc_sync(bid, 'synced')
    monkeypatch.setenv('BATCH_TEST_SETTING', 'different execution environment')
    assert batches.evidence_current(service.tasks.load(tid))
    assert not batches.transition(bid, 'done')['ok']


@pytest.mark.parametrize('content', ['{broken', '[]', '{}', '{"task_ids": "TASK-0001"}'])
def test_corrupt_batch_definition_returns_validation_error(setup, content):
    _, service, batches, task = setup
    bid = batches.create('corrupt definition', [task()])['batch']['batch_id']
    (service.data_root / 'batches' / f'{bid}.json').write_text(content)
    with pytest.raises(ValidationError):
        batches.get(bid)


def test_relative_executable_outside_task_scope_invalidates_reuse(setup):
    repo, _, batches, task = setup
    command = repo / 'check'
    command.write_text('#!/bin/sh\nexit 0\n')
    command.chmod(0o755)
    tid = task('a.py', './check')
    bid = batches.create('relative executable', [tid])['batch']['batch_id']
    assert batches.run(bid)['ok']
    command.write_text('#!/bin/sh\nexit 1\n')
    result = batches.run(bid)
    assert result['executed_count'] == 1 and not result['ok']


def test_other_project_cannot_reuse_copied_run_evidence(setup, tmp_path):
    _, service, batches, task = setup
    command = 'echo ran >> .donegate-mcp/counter'
    bid = batches.create('first project', [task(command=command)])['batch']['batch_id']
    assert batches.run(bid)['ok']
    other_repo = tmp_path / 'other-repo'
    other_repo.mkdir()
    subprocess.run(['git', 'init', '-q', str(other_repo)], check=True)
    (other_repo / 'spec.md').write_text('requirements')
    (other_repo / 'a.py').write_text('a')
    other_service = DoneGateService(other_repo / '.donegate-mcp', other_repo)
    other_service.init_project('other project', repo_root=other_repo)
    tid = other_service.create_task('task', 'spec.md', verification_mode='self-test',
                                    test_commands=[command], owned_paths=['a.py'])['task']['task_id']
    from donegate_mcp.domain.batches import BatchService
    from shutil import copytree
    copytree(service.data_root / 'batch-runs', other_service.data_root / 'batch-runs')
    other = BatchService(other_service)
    result = other.run(other.create('second project', [tid])['batch']['batch_id'])
    assert result['ok'] and result['executed_count'] == 1 and result['reused_count'] == 0
    assert (other_service.data_root / 'counter').read_text().splitlines() == ['ran']
