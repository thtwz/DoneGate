import json
import os
from pathlib import Path
import subprocess
import sys

import pytest

from test_batches import setup
from donegate_mcp.errors import TransitionError, ValidationError
from donegate_mcp.web.read_model import project_detail
from donegate_mcp.web.registry import ProjectRegistry


def test_batch_activation_supervises_union_and_task_activation_exits(setup):
    repo, service, batches, task = setup
    subprocess.run(['git', '-C', str(repo), 'add', 'a.py', 'b.py', 'spec.md'], check=True)
    subprocess.run(['git', '-C', str(repo), '-c', 'user.name=Test', '-c', 'user.email=test@example.com', 'commit', '-qm', 'baseline'], check=True)
    a, b = task('a.py'), task('b.py')
    batch = batches.create('flow', [a, b])['batch']['batch_id']
    batches.activate(batch)
    (repo / 'a.py').write_text('new a')
    (repo / 'b.py').write_text('new b')
    ctx = service.get_context(repo)['context']
    assert ctx['active_batch']['batch_id'] == batch
    assert ctx['active_task'] is None
    assert ctx['status'] == 'stale_verification'
    assert batches.run(batch)['ok']
    batches.doc_sync(batch, 'synced', notes='Reviewed documents')
    assert service.get_context(repo)['context']['policy']['pre_push']['action'] == 'allow'
    service.activate_task(a, repo)
    assert batches.active()['batch'] is None
    assert service.get_context(repo)['context']['status'] == 'task_mismatch'


def test_plain_task_entrypoints_cannot_drop_batch_dependencies(setup, tmp_path):
    repo, service, batches, task = setup
    a, b = task('a.py'), task('b.py')
    batch = batches.create('dependent', [a, b], dependencies={b: [a]})['batch']['batch_id']
    assert batches.run(batch)['ok']
    batches.doc_sync(batch, 'synced')
    assert batches.transition(batch, 'done')['ok']
    registry = ProjectRegistry(tmp_path / 'registry.json')
    entry = registry.add(str(repo))
    assert project_detail(entry)['summary']['current_verified_tasks'] == 2
    (repo / 'a.py').write_text('new prerequisite')
    projected = project_detail(entry)
    assert projected['summary']['done_tasks'] == 2
    assert projected['summary']['stale_evidence_tasks'] == 2
    assert projected['batches'][0]['batch_id'] == batch
    with pytest.raises(ValidationError, match='batch check'):
        service.run_self_test(b)
    with pytest.raises(TransitionError, match='verification'):
        service.transition_task(b, 'done')
    service.record_verification(b, 'passed', ref='standalone assertion')
    with pytest.raises(TransitionError, match='verification'):
        service.transition_task(b, 'done')
    assert service.ensure_verification(b)['ok']


def test_real_git_hook_reuses_active_batch_without_per_member_test(setup):
    repo, service, batches, task = setup
    subprocess.run(['git', '-C', str(repo), 'add', 'a.py', 'b.py', 'spec.md'], check=True)
    subprocess.run(['git', '-C', str(repo), '-c', 'user.name=Test', '-c', 'user.email=test@example.com', 'commit', '-qm', 'baseline'], check=True)
    command = 'echo run >> .donegate-mcp/counter'
    a, b = task('a.py', command), task('b.py', command)
    batch = batches.create('hook flow', [a, b])['batch']['batch_id']
    batches.activate(batch)
    assert batches.run(batch)['ok']
    batches.doc_sync(batch, 'synced')
    root = Path(__file__).resolve().parents[1]
    env = {k: v for k, v in os.environ.items() if not k.startswith('DONEGATE_MCP_') and k not in ('TASK_ID', 'BATCH_ID')}
    env.update(PYTHONPATH=str(root / 'src'), DONEGATE_MCP_ROOT=str(service.data_root), DONEGATE_MCP_REPO_ROOT=str(repo))
    hook = root / 'scripts/pre-commit.sh'
    first = subprocess.run(['bash', str(hook)], cwd=repo, env=env, capture_output=True, text=True)
    assert first.returncode == 0, first.stdout + first.stderr
    counter = (service.data_root / 'counter').read_text()
    second = subprocess.run(['bash', str(hook)], cwd=repo, env=env, capture_output=True, text=True)
    assert second.returncode == 0, second.stdout + second.stderr
    assert (service.data_root / 'counter').read_text() == counter
    assert '"executed_count": 0' in second.stdout
