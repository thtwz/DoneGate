from __future__ import annotations

import json
import subprocess
from concurrent.futures import ThreadPoolExecutor

import pytest

from donegate_mcp.cli.main import main
from donegate_mcp.domain.services import DoneGateService
from donegate_mcp.errors import ValidationError
from donegate_mcp.mcp.server import DoneGateMcpApp
from test_mcp_server import _tool


@pytest.fixture
def repos(tmp_path):
    roots = [tmp_path / name for name in ('a', 'b')]
    for root in roots:
        root.mkdir()
        subprocess.run(['git', 'init', str(root)], check=True, capture_output=True)
    return roots


def test_explicit_repo_beats_every_inherited_root(repos, monkeypatch):
    a, b = repos
    for key in ('DONEGATE_MCP_ROOT', 'DONEGATE_MCP_DATA_ROOT'):
        monkeypatch.setenv(key, str(a / '.donegate-mcp'))
    monkeypatch.setenv('DONEGATE_MCP_REPO_ROOT', str(a))
    monkeypatch.setenv('DONEGATE_MCP_WORKDIR', str(a))
    app = DoneGateMcpApp(str(a / '.donegate-mcp'))
    result = _tool(app, 'project_init')('b', repo_root=str(b))
    assert result['ok']
    assert result['project']['repo_root'] == str(b)
    assert (b / '.donegate-mcp/project.json').exists()
    assert not (a / '.donegate-mcp').exists()


def test_shared_server_requires_target_and_rejects_relative_roots(tmp_path, monkeypatch):
    for key in ('DONEGATE_MCP_ROOT', 'DONEGATE_MCP_DATA_ROOT', 'DONEGATE_MCP_REPO_ROOT', 'DONEGATE_MCP_WORKDIR'):
        monkeypatch.delenv(key, raising=False)
    monkeypatch.chdir(tmp_path)
    app = DoneGateMcpApp()
    for kwargs in ({}, {'repo_root': '.'}, {'data_root': '.donegate-mcp'}):
        result = _tool(app, 'project_init')('bad', **kwargs)
        assert result['ok'] is False
        assert result['error_code'] == 'validation_error'
        assert result['errors']
    assert list(tmp_path.iterdir()) == []


def test_two_repos_same_ids_interleaved_and_concurrent(repos):
    app = DoneGateMcpApp()
    for repo in repos:
        assert _tool(app, 'project_init')(repo.name, repo_root=str(repo))['ok']
        result = _tool(app, 'task_create')(repo.name, 'spec.md', repo_root=str(repo))
        assert result['task']['task_id'] == 'TASK-0001'
    def mutate(repo):
        for i in range(4):
            result = _tool(app, 'task_record_verification')('TASK-0001', 'passed', ref=f'{repo.name}-{i}', repo_root=str(repo))
            assert result['ok']
        return _tool(app, 'task_get')('TASK-0001', repo_root=str(repo))
    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(mutate, repos))
    for repo, result in zip(repos, results):
        assert result['task']['title'] == repo.name
        assert result['task']['last_verification_ref'] == f'{repo.name}-3'


def test_ownership_mismatch_and_init_idempotency(repos):
    a, b = repos
    app = DoneGateMcpApp()
    initial = _tool(app, 'project_init')('a', repo_root=str(a))
    _tool(app, 'task_create')('original', 'spec.md', repo_root=str(a))
    before = {str(p): p.read_bytes() for p in (a / '.donegate-mcp').rglob('*') if p.is_file()}
    for tool, args in [('task_create', ('bad', 'spec.md')), ('project_init', ('bad',))]:
        result = _tool(app, tool)(*args, repo_root=str(b), data_root=str(a / '.donegate-mcp'))
        assert not result['ok']
    assert before == {str(p): p.read_bytes() for p in (a / '.donegate-mcp').rglob('*') if p.is_file()}
    same = _tool(app, 'project_init')('a renamed?', repo_root=str(a))
    assert same['project']['project_id'] == initial['project']['project_id']
    next_task = _tool(app, 'task_create')('next', 'spec.md', repo_root=str(a))
    assert next_task['task']['task_id'] == 'TASK-0002'
    with pytest.raises(ValidationError):
        DoneGateService(a / '.donegate-mcp').init_project('b', repo_root=b)


def test_cli_global_target_and_legacy_placement(repos, tmp_path, monkeypatch, capsys):
    a, b = repos
    monkeypatch.chdir(tmp_path)
    assert main(['--repo-root', str(b), '--json', 'init', '--project-name', 'b']) == 0
    capsys.readouterr()
    assert main(['--repo-root', str(b), '--json', '--compact', 'task', 'create', '--title', 'b-task', '--spec-ref', 'spec.md']) == 0
    task = json.loads(capsys.readouterr().out)['task']
    assert task['task_id'] == 'TASK-0001'
    assert 'history' not in task
    assert main(['--json', 'task', 'activate', 'TASK-0001', '--repo-root', str(b)]) == 0
    capsys.readouterr()
    assert main(['--repo-root', str(b), '--json', 'task', 'show', 'TASK-0001']) == 0
    assert json.loads(capsys.readouterr().out)['task']['title'] == 'b-task'
    assert not (tmp_path / '.donegate-mcp').exists()
    assert not (a / '.donegate-mcp').exists()


def test_context_is_focused_and_full_task_is_lazy(repos):
    repo = repos[0]
    app = DoneGateMcpApp()
    _tool(app, 'project_init')('a', repo_root=str(repo))
    task = _tool(app, 'task_create')('active', 'spec.md', required_doc_refs=['docs.md'], repo_root=str(repo))['task']
    _tool(app, 'task_create')('unrelated', 'other.md', repo_root=str(repo))
    assert _tool(app, 'task_activate')(task['task_id'], repo_root=str(repo))['ok']
    payload = _tool(app, 'project_context')(repo_root=str(repo))
    assert payload['ok']
    context = payload['context']
    assert context['repo_root'] == str(repo)
    assert context['data_root'] == str(repo / '.donegate-mcp')
    assert context['active_task']['task_id'] == task['task_id']
    assert 'tasks' not in context
    assert 'required_doc_refs' not in context['active_task']
    assert 'policy' in context and 'blockers' in context and 'next_action' in context
    full = _tool(app, 'task_get')(task['task_id'], repo_root=str(repo))
    assert full['task']['required_doc_refs'] == [str(repo / 'docs.md')]


def test_compact_preserves_errors_and_important_facts(repos):
    app = DoneGateMcpApp()
    repo = str(repos[0])
    _tool(app, 'project_init')('a', repo_root=repo)
    full = _tool(app, 'task_create')('a', 'spec.md', summary='x' * 3000, repo_root=repo)
    compact = _tool(app, 'task_record_verification')('TASK-0001', 'failed', ref='failure.log', repo_root=repo, compact=True)
    assert compact['task']['verification_status'] == 'failed'
    assert compact['task']['last_verification_ref'] == 'failure.log'
    assert compact['task']['doc_sync_status']
    assert len(json.dumps(compact)) < len(json.dumps(full)) / 2
    error = _tool(app, 'task_transition')('TASK-0001', 'done', repo_root=repo, compact=True)
    assert not error['ok'] and error['errors']


def test_explicit_data_only_ignores_inherited_repo(repos, monkeypatch):
    a, b = repos
    DoneGateService(b / '.donegate-mcp').init_project('b', repo_root=b)
    monkeypatch.setenv('DONEGATE_MCP_REPO_ROOT', str(a))
    monkeypatch.setenv('DONEGATE_MCP_ROOT', str(a / '.donegate-mcp'))
    app = DoneGateMcpApp()
    result = _tool(app, 'task_create')('belongs-to-b', 'spec.md', data_root=str(b / '.donegate-mcp'))
    assert result['ok']
    assert result['task']['spec_ref'] == str(b / 'spec.md')
    assert not (a / '.donegate-mcp').exists()


def test_compact_self_test_runs_in_target_and_retains_log_ref(repos, tmp_path, monkeypatch):
    a, b = repos
    monkeypatch.chdir(tmp_path)
    app = DoneGateMcpApp()
    _tool(app, 'project_init')('b', repo_root=str(b))
    _tool(app, 'task_create')('b', 'spec.md', test_commands=['pwd'], repo_root=str(b))
    result = _tool(app, 'task_run_self_test')('TASK-0001', repo_root=str(b), compact=True)
    assert result['exit_code'] == 0
    assert result['self_test']['exit_code'] == 0
    from pathlib import Path
    assert str(b) in Path(result['self_test']['ref']).read_text()
    assert result['task']['last_verification_ref'] == result['self_test']['ref']
    for workdir in (str(a), '.'):
        result = _tool(app, 'task_run_self_test')('TASK-0001', repo_root=str(b), workdir=workdir, compact=True)
        assert not result['ok'] and result['errors']


def test_cli_context_output_and_global_target_survives_subcommand_defaults(repos, capsys):
    repo = str(repos[0])
    assert main(['--repo-root', repo, 'init', '--project-name', 'a']) == 0
    capsys.readouterr()
    assert main(['--repo-root', repo, '--json', 'context']) == 0
    context = json.loads(capsys.readouterr().out)['context']
    assert context['repo_root'] == repo
    assert context['active_task'] is None
    assert main(['--repo-root', repo, 'context']) == 0
    assert repo in capsys.readouterr().out


def test_compact_presenter_preserves_warnings_and_self_test_status():
    from donegate_mcp.compact import compact_payload
    result = compact_payload({'ok': False, 'warnings': ['compatibility'], 'errors': ['failed'], 'exit_code': 7, 'self_test': {'exit_code': 7, 'ref': 'log', 'commands': ['very long command' * 100], 'stdout_path': 'log'}, 'unused': None})
    assert result['errors'] == ['failed']
    assert result['warnings'] == ['compatibility']
    assert result['self_test']['exit_code'] == 7
    assert result['self_test']['ref'] == 'log'
    assert 'commands' not in result['self_test']
    assert 'unused' not in result


def test_invalid_data_file_is_structured_error_without_mutation(repos, tmp_path):
    target = tmp_path / 'not-a-directory'
    target.write_text('preserve me')
    result = _tool(DoneGateMcpApp(), 'project_init')('bad', data_root=str(target))
    assert result['ok'] is False
    assert result['error_code'] == 'validation_error'
    assert target.read_text() == 'preserve me'


def test_context_includes_completion_gate_when_git_is_clean(repos):
    repo = repos[0]
    (repo / '.gitignore').write_text('.donegate-mcp/\n')
    subprocess.run(['git', '-C', str(repo), 'add', '.gitignore'], check=True, capture_output=True)
    subprocess.run(['git', '-C', str(repo), '-c', 'user.email=t@example.com', '-c', 'user.name=Test', 'commit', '-m', 'initial'], check=True, capture_output=True)
    app = DoneGateMcpApp()
    _tool(app, 'project_init')('a', repo_root=str(repo))
    _tool(app, 'task_create')('active', 'spec.md', repo_root=str(repo))
    _tool(app, 'task_activate')('TASK-0001', repo_root=str(repo))
    _tool(app, 'task_block')('TASK-0001', 'waiting on dependency', repo_root=str(repo))
    context = _tool(app, 'project_context')(repo_root=str(repo))['context']
    assert context['blockers']
    assert 'unblock' in context['next_action']


def test_cli_check_reuses_current_verification(repos, capsys):
    repo = str(repos[0])
    service = DoneGateService(repos[0] / '.donegate-mcp')
    service.init_project('a', repo_root=repo)
    service.create_task('a', 'spec.md')
    service.record_verification('TASK-0001', 'passed', ref='manual-review')
    assert main(['--repo-root', repo, '--json', '--compact', 'task', 'check', 'TASK-0001']) == 0
    result = json.loads(capsys.readouterr().out)
    assert result['reused'] is True
    assert result['task']['verification_status'] == 'passed'


def test_context_completed_task_has_final_action_and_ownership(repos):
    repo = repos[0]
    app = DoneGateMcpApp()
    _tool(app, 'project_init')('a', repo_root=str(repo))
    _tool(app, 'task_create')('active', 'spec.md', owned_paths=['.'], repo_root=str(repo))
    _tool(app, 'task_activate')('TASK-0001', repo_root=str(repo))
    _tool(app, 'task_record_verification')('TASK-0001', 'passed', repo_root=str(repo))
    _tool(app, 'task_record_doc_sync')('TASK-0001', 'synced', repo_root=str(repo))
    _tool(app, 'task_transition')('TASK-0001', 'done', repo_root=str(repo))
    context = _tool(app, 'project_context')(repo_root=str(repo))['context']
    assert context['active_task']['owned_paths'] == ['.']
    assert 'complete' in context['next_action']
    assert 'task_get' not in context['next_action']


def test_cli_default_cwd_store_checks_current_repo_ownership(repos, monkeypatch, capsys):
    a, b = repos
    service = DoneGateService(a / '.donegate-mcp')
    service.init_project('belongs-to-b', repo_root=b)
    before = {str(path): path.read_bytes() for path in (a / '.donegate-mcp').rglob('*') if path.is_file()}
    monkeypatch.chdir(a)
    assert main(['--json', 'task', 'create', '--title', 'wrong-project', '--spec-ref', 'spec.md']) == 2
    payload = json.loads(capsys.readouterr().out)
    assert not payload['ok']
    assert 'ownership mismatch' in payload['errors'][0]
    assert before == {str(path): path.read_bytes() for path in (a / '.donegate-mcp').rglob('*') if path.is_file()}


@pytest.mark.parametrize('command', ['self-test', 'check'])
def test_cli_failed_test_command_returns_failure_status(repos, capsys, command):
    repo = repos[0]
    service = DoneGateService(repo / '.donegate-mcp')
    service.init_project('a', repo_root=repo)
    service.create_task('failed check', 'spec.md', verification_mode='self-test', test_commands=['false'])
    assert main(['--repo-root', str(repo), '--json', '--compact', 'task', command, 'TASK-0001']) != 0
    result = json.loads(capsys.readouterr().out)
    assert result['exit_code'] == 1
    assert result['task']['verification_status'] == 'failed'
