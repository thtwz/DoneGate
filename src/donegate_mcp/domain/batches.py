"""Explicit development batches and durable, coverage-bound command reuse."""
from __future__ import annotations

from copy import deepcopy
from contextlib import contextmanager
import hashlib
import inspect
import json
import os
from pathlib import Path
import re
import shlex
import shutil
import subprocess
import sys
from typing import Any
from uuid import uuid4

from donegate_mcp.domain.evidence import input_snapshot
from donegate_mcp.domain.lifecycle import require_transition
from donegate_mcp.errors import DoneGateMcpError, ValidationError
from donegate_mcp.models import Task, TaskStatus, VerificationStatus, utc_now
from donegate_mcp.storage.fs import atomic_write_json, ensure_dir, read_json
from donegate_mcp.storage.project_store import ProjectStore
from donegate_mcp.config import TASKS_DIRNAME


def _hash(value: Any) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=True).encode()).hexdigest()


def _execution_environment() -> dict[str, str]:
    # Shell/terminal and agent transport metadata vary between equivalent CLI,
    # hook, and dashboard processes. Runtime and application settings remain inputs.
    volatile = {'_', 'SHLVL', 'PWD', 'OLDPWD', 'PYTEST_CURRENT_TEST', 'TERM',
                'TERM_PROGRAM', 'TERM_PROGRAM_VERSION', 'TERM_SESSION_ID', 'COLORTERM',
                'COLUMNS', 'LINES', 'PS1', 'PS2', 'PROMPT', 'RPS1'}
    return {key: value for key, value in os.environ.items()
            if key not in volatile and not key.startswith(('CODEX_', 'XPC_', 'ITERM_', 'VSCODE_'))}


class _Evidence:
    """Read-only fingerprints shared by runtime and dashboard projections."""
    def __init__(self, repo: Path, data_root: Path, *, memoize=False):
        self.repo, self.data_root = (repo.resolve() if repo else None), data_root.resolve()
        self.project_id = ProjectStore(self.data_root).load().project_id
        self.memoize = memoize
        self._cache = {}

    @contextmanager
    def read_phase(self):
        previous, previous_cache = self.memoize, self._cache
        self.memoize, self._cache = True, {}
        try:
            yield self
        finally:
            self.memoize, self._cache = previous, previous_cache

    def load_task(self, task_id: str) -> Task:
        if not re.fullmatch(r'TASK-\d+', task_id):
            raise ValidationError('invalid task ID in batch evidence')
        key = ('task', task_id)
        if self.memoize and key in self._cache:
            return self._cache[key]
        task = Task.from_dict(read_json(self.data_root / TASKS_DIRNAME / f'{task_id}.json'))
        if self.memoize:
            self._cache[key] = task
        return task

    def snapshot(self, task: Task) -> str | None:
        if self.repo is None:
            return None
        key = ('snapshot', task.task_id)
        if self.memoize and key in self._cache:
            return self._cache[key]
        conservative = deepcopy(task)
        if task.owned_paths:
            from donegate_mcp.domain.evidence import _matches
            listing = subprocess.run(['git', '-C', str(self.repo), 'ls-files', '-z', '--cached', '--others', '--exclude-standard'], capture_output=True)
            if listing.returncode:
                return None
            paths = [os.fsdecode(p) for p in listing.stdout.split(b'\0') if p]
            if any(not any(_matches(path, scope) for path in paths) for scope in task.owned_paths):
                conservative.owned_paths = []
        result = input_snapshot(conservative, self.repo, self.data_root)
        if self.memoize:
            self._cache[key] = result
        return result

    def acceptance_snapshot(self, task: Task) -> str | None:
        """Manual facts bind to source/protocol/dependencies, independent of process env."""
        inputs, visiting = {}, set()
        root_definition = read_json(self.data_root / 'batches' / f'{task.batch_id}.json') if task.batch_id else None
        def visit(task_id):
            if task_id in visiting:
                return False
            if task_id in inputs:
                return True
            member = task if task_id == task.task_id else self.load_task(task_id)
            definition = root_definition if root_definition and task_id in root_definition['task_ids'] else (
                read_json(self.data_root / 'batches' / f'{member.batch_id}.json') if member.batch_id else None)
            deps = definition['dependencies'].get(task_id, []) if definition else []
            snapshot = self.snapshot(member)
            if snapshot is None:
                return False
            visiting.add(task_id)
            if not all(visit(dep) for dep in deps):
                return False
            visiting.remove(task_id)
            inputs[task_id] = {'snapshot': snapshot, 'dependencies': deps}
            return True
        return _hash({'project': self.project_id, 'inputs': inputs}) if visit(task.task_id) else None

    def fingerprint(self, command: str, task_ids: list[str], dependencies: dict[str, list[str]], mode: str, environment_hash: str | None = None) -> str | None:
        key = ('fingerprint', _hash([command, task_ids, dependencies, mode, environment_hash or _hash(_execution_environment())]))
        if self.memoize and key in self._cache:
            return self._cache[key]
        inputs: dict[str, Any] = {}
        def visit(task_id: str) -> bool:
            if task_id in inputs:
                return True
            task = self.load_task(task_id)
            snapshot = self.snapshot(task)
            if snapshot is None:
                return False
            inputs[task_id] = {'snapshot': snapshot, 'dependencies': dependencies.get(task_id, [])}
            return all(visit(dep) for dep in dependencies.get(task_id, []))
        if not all(visit(task_id) for task_id in task_ids):
            return None
        executables = [sys.executable, '/bin/sh']
        try:
            tokens = shlex.split(command)
            executable = None
            if tokens:
                if '/' in tokens[0]:
                    candidate = Path(tokens[0])
                    candidate = candidate if candidate.is_absolute() else self.repo / candidate
                    executable = str(candidate) if candidate.is_file() else None
                else:
                    executable = shutil.which(tokens[0])
            if executable:
                executables.append(executable)
        except ValueError:
            pass
        runtime = []
        for path in executables:
            file = Path(path)
            stat = file.stat()
            runtime.append((str(file.resolve()), stat.st_size, stat.st_mtime_ns, hashlib.sha256(file.read_bytes()).hexdigest()))
        # Dependency manifests can affect a scoped command even outside its source scope.
        manifests = {}
        for name in ('pyproject.toml', 'uv.lock', 'poetry.lock', 'requirements.txt', 'package.json', 'package-lock.json', 'pnpm-lock.yaml', 'yarn.lock', 'Cargo.lock', 'go.sum'):
            path = self.repo / name
            if path.is_file():
                manifests[name] = hashlib.sha256(path.read_bytes()).hexdigest()
        result = _hash({'version': 1, 'project': self.project_id, 'repo': str(self.repo), 'command': command,
                      'mode': mode, 'inputs': inputs, 'environment': environment_hash or _hash(_execution_environment()),
                      'python': sys.version, 'runtime': runtime, 'manifests': manifests})
        if self.memoize:
            self._cache[key] = result
        return result

    def check_current(self, check: dict[str, Any], dependencies: dict[str, list[str]], mode: str, *, live_environment=False) -> bool:
        if not check.get('ok') or not check.get('fingerprint'):
            return False
        key = ('check', _hash([check, dependencies, mode, live_environment]))
        if self.memoize and key in self._cache:
            return self._cache[key]
        for label in ('stdout', 'stderr'):
            path = Path(check[f'{label}_path']).resolve()
            if not path.is_relative_to(self.data_root / 'artifacts' / 'batches') or not path.is_file():
                return False
            if hashlib.sha256(path.read_bytes()).hexdigest() != check.get(f'{label}_hash'):
                return False
        result = check['fingerprint'] == self.fingerprint(check['command'], check['task_ids'], dependencies, mode,
                                                                  None if live_environment else check.get('environment_hash'))
        if self.memoize:
            self._cache[key] = result
        return result

    def current(self, task: Task, visiting: set[str] | None = None, *, live_environment=False) -> bool:
        key = ('current', task.task_id, live_environment)
        if self.memoize and key in self._cache:
            return self._cache[key]
        result = self._current(task, visiting, live_environment=live_environment)
        if self.memoize:
            self._cache[key] = result
        return result

    def _current(self, task: Task, visiting: set[str] | None = None, *, live_environment=False) -> bool:
        ref = Path(task.last_verification_ref or '')
        run_dir = self.data_root / 'batch-runs'
        if not ref.is_absolute() or ref.parent != run_dir:
            return not getattr(task, 'batch_id', None)
        visiting = set(visiting or ())
        if task.task_id in visiting:
            return False
        visiting.add(task.task_id)
        try:
            run = read_json(ref)
            if run.get('project_id') != self.project_id:
                return False
            if task.batch_id:
                if run.get('batch_id') != task.batch_id:
                    return False
                definition = read_json(self.data_root / 'batches' / f'{task.batch_id}.json')
                if task.task_id not in definition['task_ids'] or run['selected_mode'] != definition['selected_mode']:
                    return False
                if any(run['dependencies'].get(tid, []) != definition['dependencies'].get(tid, []) for tid in definition['task_ids']):
                    return False
            outcome = next(row for row in run['tasks'] if row['task_id'] == task.task_id)
            if not outcome['ok']:
                return False
            covered = [c for c in run['checks'] if task.task_id in c['task_ids']]
            if set(c['command'] for c in covered) != set(task.test_commands):
                return False
            if task.verification_mode != 'self-test':
                acceptance = run.get('manual_acceptance', {}).get(task.task_id)
                if not acceptance or acceptance['input_hash'] != input_snapshot(task, self.repo, self.data_root):
                    return False
                retained = getattr(task, 'manual_acceptance_input_hash', None)
                if not retained or acceptance.get('acceptance_hash') != retained or retained != self.acceptance_snapshot(task):
                    return False
                if acceptance.get('fingerprint') != self.fingerprint('', [task.task_id], run['dependencies'],
                                                                    run['selected_mode'], None if live_environment else acceptance.get('environment_hash')):
                    return False
            elif not covered:
                return False
            if not all(self.check_current(c, run['dependencies'], run['selected_mode'], live_environment=live_environment) for c in covered):
                return False
            for dep_id in run['dependencies'].get(task.task_id, []):
                dep = self.load_task(dep_id)
                if dep.verification_status != VerificationStatus.PASSED or dep.blocked_reason or dep.needs_revalidation:
                    return False
                if input_snapshot(dep, self.repo, self.data_root) != dep.verification_input_hash or not self.current(dep, visiting, live_environment=live_environment):
                    return False
            return True
        except (DoneGateMcpError, OSError, ValueError, KeyError, StopIteration, TypeError):
            return False


def manual_acceptance_snapshot(task: Task, repo: Path, data_root: Path) -> str | None:
    """Pure conservative snapshot for explicitly observed manual acceptance."""
    return _Evidence(repo, data_root).acceptance_snapshot(task)


def batch_evidence_reader(repo: Path, data_root: Path) -> _Evidence:
    """Create one memoized reader per locked dashboard read; discard after use."""
    return _Evidence(repo, data_root, memoize=True)


def evidence_current_read(task: Task, repo: Path, data_root: Path) -> bool:
    """Check durable batch evidence without initializing or mutating service state."""
    ref = Path(task.last_verification_ref or '')
    if not ref.is_absolute() or ref.parent != data_root.resolve() / 'batch-runs':
        return not getattr(task, 'batch_id', None)
    return _Evidence(repo, data_root).current(task)


class BatchService:
    def __init__(self, service):
        self.service = service
        project = service._require_project()
        self.repo = service._resolve_repo_root(None, project=project, data_root=service.data_root)
        self.data_root = service.data_root
        self.definitions = self.data_root / 'batches'
        self.runs = self.data_root / 'batch-runs'
        self.evidence = _Evidence(self.repo, self.data_root)

    def evidence_current(self, task: Task, *, live_environment=False) -> bool:
        return self.evidence.current(task, live_environment=live_environment)

    def _load(self, batch_id: str) -> dict[str, Any]:
        if not isinstance(batch_id, str) or not re.fullmatch(r'BATCH-[a-f0-9]+', batch_id):
            raise ValidationError(f'invalid batch ID: {batch_id}')
        try:
            batch = read_json(self.definitions / f'{batch_id}.json')
        except (DoneGateMcpError, ValueError, UnicodeError) as exc:
            raise ValidationError(f'unknown or unreadable batch: {batch_id}') from exc
        if not isinstance(batch, dict):
            raise ValidationError(f'invalid batch definition: {batch_id}')
        if (batch.get('batch_id') != batch_id or not isinstance(batch.get('title'), str)
                or not isinstance(batch.get('task_ids'), list) or not batch['task_ids']
                or not all(isinstance(tid, str) for tid in batch['task_ids'])
                or not isinstance(batch.get('dependencies'), dict)
                or not all(isinstance(v, list) and all(isinstance(t, str) for t in v) for v in batch['dependencies'].values())
                or batch.get('selected_mode') not in ('single', 'batch')):
            raise ValidationError(f'invalid batch definition: {batch_id}')
        if batch.get('project_id') != self.evidence.project_id:
            raise ValidationError('batch belongs to another project')
        return batch

    def _expanded_dependencies(self, task_ids, dependencies):
        graph = deepcopy(dependencies)
        pending = [dep for values in dependencies.values() for dep in values]
        seen = set(task_ids)
        while pending:
            tid = pending.pop()
            if tid in seen:
                continue
            seen.add(tid)
            if not isinstance(tid, str) or not re.fullmatch(r'TASK-\d+', tid):
                raise ValidationError('invalid external prerequisite ID')
            try:
                task = self.service.tasks.load(tid)
            except DoneGateMcpError as exc:
                raise ValidationError(f'unknown prerequisite: {tid}') from exc
            if task.batch_id:
                definition = self._load(task.batch_id)
                values = definition['dependencies'].get(tid, [])
                if not isinstance(values, list) or not all(isinstance(v, str) for v in values):
                    raise ValidationError('invalid persisted dependency graph')
                graph[tid] = values
                pending.extend(values)
        return graph

    def _validate(self, task_ids, dependencies):
        if not isinstance(task_ids, list) or not task_ids or not all(isinstance(t, str) for t in task_ids):
            raise ValidationError('task_ids must be a nonempty list of task IDs')
        if len(set(task_ids)) != len(task_ids):
            raise ValidationError('duplicate batch members')
        if not isinstance(dependencies, dict) or any(t not in task_ids for t in dependencies):
            raise ValidationError('dependency keys must be batch members')
        for values in dependencies.values():
            if not isinstance(values, list) or not all(isinstance(t, str) for t in values) or len(set(values)) != len(values):
                raise ValidationError('dependencies must contain unique task IDs')
        all_ids = set(task_ids) | {dep for deps in dependencies.values() for dep in deps}
        for task_id in all_ids:
            if not re.fullmatch(r'TASK-\d+', task_id):
                raise ValidationError(f'invalid task ID: {task_id}')
            try:
                self.service.tasks.load(task_id)
            except DoneGateMcpError as exc:
                raise ValidationError(f'unknown task: {task_id}') from exc
        graph = self._expanded_dependencies(task_ids, dependencies)
        ordered, visiting = [], set()
        def visit(task_id):
            if task_id in visiting:
                raise ValidationError('dependency cycle')
            if task_id in ordered:
                return
            visiting.add(task_id)
            for dep in graph.get(task_id, []):
                visit(dep)
            visiting.remove(task_id)
            ordered.append(task_id)
        for task_id in task_ids:
            visit(task_id)
        return ordered

    def create(self, title, task_ids, mode='auto', rationale='', dependencies=None, risk='normal'):
        with self.service.write_lock:
            if not isinstance(title, str) or not title.strip():
                raise ValidationError('batch title is required')
            if mode not in ('auto', 'single', 'batch') or risk not in ('normal', 'high'):
                raise ValidationError('mode must be auto|single|batch and risk normal|high')
            if not isinstance(rationale, str):
                raise ValidationError('rationale must be a string')
            deps = {} if dependencies is None else dependencies
            self._validate(task_ids, deps)
            recommended = 'single' if len(task_ids) == 1 or risk == 'high' else 'batch'
            if mode != 'auto' and mode != recommended and not rationale.strip():
                raise ValidationError('overriding automatic mode requires a rationale')
            selected = recommended if mode == 'auto' else mode
            batch = {'batch_id': f'BATCH-{uuid4().hex[:12]}', 'project_id': self.evidence.project_id,
                     'title': title.strip(), 'task_ids': list(task_ids), 'requested_mode': mode, 'selected_mode': selected,
                     'rationale': rationale or ('Single task or high risk' if selected == 'single' else 'Multiple normal-risk tasks share declared verification'),
                     'dependencies': deepcopy(deps), 'risk': risk, 'created_at': utc_now(), 'latest_run': None}
            atomic_write_json(self.definitions / f"{batch['batch_id']}.json", batch)
            for tid in task_ids:
                task = self.service.tasks.load(tid)
                legacy_manual_pass = (task.verification_mode != 'self-test' and not task.manual_acceptance_input_hash
                                      and task.verification_status == VerificationStatus.PASSED
                                      and task.verification_input_hash == self.service._input_snapshot(task))
                task.batch_id = batch['batch_id']
                if legacy_manual_pass:
                    task.manual_acceptance_input_hash = self.evidence.acceptance_snapshot(task)
                    task.manual_acceptance_ref = task.last_verification_ref
                task.updated_at = utc_now()
                self.service.tasks.save(task)
                self.service._emit(tid, 'batch_membership_changed', {'batch_id': batch['batch_id']})
            self.service._sync_state_files()
            return {'ok': True, 'batch': batch, 'errors': []}

    def list(self):
        self.service._require_project()
        return {'ok': True, 'batches': [self._load(path.stem) for path in sorted(self.definitions.glob('BATCH-*.json'))], 'errors': []}

    def get(self, batch_id):
        return {'ok': True, 'batch': self._load(batch_id), 'errors': []}

    def _bulk(self, batch_id, operation):
        batch = self._load(batch_id)
        self._validate(batch['task_ids'], batch['dependencies'])
        results = []
        for task_id in batch['task_ids']:
            try:
                result = operation(task_id)
                results.append({'task_id': task_id, 'ok': result['ok'], 'status': result['task']['status'], 'errors': result.get('errors', [])})
            except (DoneGateMcpError, OSError) as exc:
                results.append({'task_id': task_id, 'ok': False, 'errors': [str(exc)]})
        errors = [error for row in results for error in row['errors']]
        return {'ok': not errors, 'batch': batch, 'tasks': results, 'errors': errors}

    def transition(self, batch_id, target_status):
        with self.service.write_lock:
            batch = self._load(batch_id)
            self._validate(batch['task_ids'], batch['dependencies'])
            target = self.service._normalize_task_status(target_status)
            if target == TaskStatus.BLOCKED:
                raise ValidationError('block individual tasks with a reason')
            # Validate copies first: one rejected member cannot transition earlier members.
            errors = []
            for tid in batch['task_ids']:
                task = self.service.tasks.load(tid)
                if target in (TaskStatus.VERIFIED, TaskStatus.DOCUMENTED, TaskStatus.DONE):
                    if not self._passed(task):
                        errors.append(f'{tid} requires current passed verification')
                try:
                    require_transition(task, target)
                except DoneGateMcpError as exc:
                    errors.append(str(exc))
            if errors:
                return {'ok': False, 'batch': batch, 'tasks': [], 'errors': errors}
            return self._bulk(batch_id, lambda tid: self.service.transition_task(tid, target_status))

    def doc_sync(self, batch_id, result, ref=None, notes=None):
        with self.service.write_lock:
            self.service._normalize_doc_sync_status(result)
            return self._bulk(batch_id, lambda tid: self.service.record_doc_sync(tid, result, ref=ref, notes=notes))

    def _passed(self, task):
        return (task.verification_status == VerificationStatus.PASSED and not task.blocked_reason
                and not task.needs_revalidation and self.service._input_snapshot(task) == task.verification_input_hash
                and self.evidence_current(task, live_environment=True))

    def run(self, batch_id, force=False):
        with self.service.write_lock:
            batch = self._load(batch_id)
            ordered = self._validate(batch['task_ids'], batch['dependencies'])
            dependencies = self._expanded_dependencies(batch['task_ids'], batch['dependencies'])
            members = {tid: self.service.tasks.load(tid) for tid in ordered if tid in batch['task_ids']}
            if any(task.batch_id != batch_id for task in members.values()):
                raise ValidationError('a member has been assigned to a newer batch; use its current batch')
            before = {tid: self.service._input_snapshot(task) for tid, task in members.items()}
            with self.evidence.read_phase():
                manual_pass = {tid: (bool(task.manual_acceptance_input_hash)
                                     and task.manual_acceptance_input_hash == self.evidence.acceptance_snapshot(task)
                                     and not task.blocked_reason and not task.needs_revalidation)
                               for tid, task in members.items() if task.verification_mode != 'self-test'}
            manual_fingerprints = {tid: self.evidence.fingerprint('', [tid], dependencies, batch['selected_mode'])
                                   for tid in manual_pass}
            manual_environment = _hash(_execution_environment())
            groups = {}
            for tid, task in members.items():
                for command in dict.fromkeys(task.test_commands):
                    key = (command, tid if batch['selected_mode'] == 'single' else '')
                    groups.setdefault(key, []).append(tid)
            run_id = f'RUN-{uuid4().hex}'
            artifact_dir = ensure_dir(self.data_root / 'artifacts' / 'batches' / run_id)
            checks = []
            old_checks = []
            if not force:
                for path in sorted(self.runs.glob('RUN-*.json')):
                    try:
                        old = read_json(path)
                        if old.get('project_id') == self.evidence.project_id:
                            old_checks.extend(old.get('checks', []))
                    except (DoneGateMcpError, ValueError):
                        continue
            for index, ((command, _), tids) in enumerate(groups.items()):
                fingerprint = self.evidence.fingerprint(command, tids, dependencies, batch['selected_mode'])
                cached = next((c for c in reversed(old_checks) if c.get('fingerprint') == fingerprint and
                               c.get('command') == command and c.get('task_ids') == tids and
                               self.evidence.check_current(c, dependencies, batch['selected_mode'], live_environment=True)), None)
                if cached:
                    check = dict(cached, reused=True, reused_from=cached.get('source_run_id'))
                else:
                    stdout_path, stderr_path = artifact_dir / f'{index}.stdout.log', artifact_dir / f'{index}.stderr.log'
                    try:
                        completed = subprocess.run(command, shell=True, cwd=self.repo, capture_output=True, text=True)
                        code, stdout, stderr = completed.returncode, completed.stdout, completed.stderr
                    except (OSError, ValueError) as exc:
                        code, stdout, stderr = 1, '', str(exc)
                    stdout_path.write_text(stdout, encoding='utf-8')
                    stderr_path.write_text(stderr, encoding='utf-8')
                    stable = fingerprint is not None and fingerprint == self.evidence.fingerprint(command, tids, dependencies, batch['selected_mode'])
                    check = {'command': command, 'task_ids': tids, 'fingerprint': fingerprint, 'exit_code': code,
                             'ok': code == 0 and stable, 'reused': False, 'source_run_id': run_id,
                             'environment_hash': _hash(_execution_environment()),
                             'reason': 'passed' if code == 0 and stable else ('inputs changed or unavailable' if not stable else 'command failed'),
                             'stdout_path': str(stdout_path), 'stderr_path': str(stderr_path),
                             'stdout_hash': hashlib.sha256(stdout.encode()).hexdigest(), 'stderr_hash': hashlib.sha256(stderr.encode()).hexdigest()}
                checks.append(check)
            # A later command may mutate inputs of an earlier executed or reused check.
            with self.evidence.read_phase():
                for check in checks:
                    if check['ok'] and not self.evidence.check_current(check, dependencies, batch['selected_mode'], live_environment=True):
                        check.update(ok=False, reason='inputs changed during batch')
            outcomes = {}
            for tid in ordered:
                if tid not in members:
                    outcomes[tid] = {'ok': self._passed(self.service.tasks.load(tid))}
                    continue
                task = members[tid]
                errors = []
                if task.blocked_reason:
                    errors.append('task is blocked')
                if not task.test_commands and task.verification_mode == 'self-test':
                    errors.append('task has no explicit test_commands coverage')
                for check in checks:
                    if tid in check['task_ids'] and not check['ok']:
                        errors.append(f"{check['command']}: {check['reason']}")
                if tid in manual_fingerprints and manual_fingerprints[tid] != self.evidence.fingerprint('', [tid], dependencies, batch['selected_mode']):
                    errors.append('manual acceptance inputs changed during batch')
                if tid in manual_pass and not manual_pass[tid]:
                    errors.append('current manual acceptance is required')
                if before[tid] is None or before[tid] != self.service._input_snapshot(self.service.tasks.load(tid)):
                    errors.append('verification inputs changed or unavailable')
                for dep in dependencies.get(tid, []):
                    if not outcomes[dep]['ok']:
                        errors.append(f'prerequisite {dep} lacks current passed verification')
                outcomes[tid] = {'task_id': tid, 'ok': not errors, 'errors': errors,
                                 'verification_status': 'passed' if not errors else 'failed'}
            rows = [outcomes[tid] for tid in batch['task_ids']]
            errors = [f"{row['task_id']}: {error}" for row in rows for error in row['errors']]
            run = {'run_id': run_id, 'project_id': self.evidence.project_id, 'batch_id': batch_id,
                   'created_at': utc_now(), 'selected_mode': batch['selected_mode'], 'dependencies': dependencies,
                   'ok': not errors, 'errors': errors, 'tasks': rows, 'checks': checks,
                   'manual_acceptance': {tid: {'input_hash': before[tid], 'ref': members[tid].manual_acceptance_ref,
                                              'acceptance_hash': members[tid].manual_acceptance_input_hash,
                                              'fingerprint': manual_fingerprints[tid], 'environment_hash': manual_environment}
                                         for tid, passed in manual_pass.items() if passed},
                   'executed_count': sum(not c['reused'] for c in checks), 'reused_count': sum(c['reused'] for c in checks)}
            run_path = self.runs / f'{run_id}.json'
            for tid in batch['task_ids']:
                # The run links accepted manual facts and all explicit command evidence.
                recorded = self.service.record_verification(tid, outcomes[tid]['verification_status'], ref=str(run_path),
                                                            notes=f'Batch {batch_id}', expected_input_hash=before[tid])
                if outcomes[tid]['ok'] and recorded['task']['verification_status'] != 'passed':
                    outcomes[tid].update(ok=False, verification_status='failed')
                    outcomes[tid]['errors'].append('inputs changed before evidence recording')
            with self.evidence.read_phase():
                final_checks = {id(c): self.evidence.check_current(c, dependencies, batch['selected_mode'], live_environment=True) for c in checks}
            for tid in ordered:
                if tid not in members:
                    outcomes[tid]['ok'] = self._passed(self.service.tasks.load(tid))
                    continue
                if not outcomes[tid]['ok']:
                    continue
                valid = before[tid] == self.service._input_snapshot(self.service.tasks.load(tid))
                valid = valid and all(final_checks[id(c)] for c in checks if tid in c['task_ids'])
                valid = valid and all(outcomes[dep]['ok'] for dep in dependencies.get(tid, []))
                if tid in manual_fingerprints:
                    valid = valid and manual_fingerprints[tid] == self.evidence.fingerprint('', [tid], dependencies, batch['selected_mode'])
                if not valid:
                    outcomes[tid].update(ok=False, verification_status='failed')
                    outcomes[tid]['errors'].append('inputs changed while recording batch evidence')
                    self.service.record_verification(tid, 'failed', ref=str(run_path), notes='batch evidence changed')
            run['errors'] = [f"{row['task_id']}: {error}" for row in rows for error in row['errors']]
            run['ok'] = not run['errors']
            atomic_write_json(run_path, run)
            for tid in batch['task_ids']:
                self.service._emit(tid, 'batch_check_recorded', {'run_id': run_id, 'ok': outcomes[tid]['ok'], 'ref': str(run_path)})
            batch['latest_run'] = {k: run[k] for k in ('run_id', 'created_at', 'ok', 'executed_count', 'reused_count')}
            atomic_write_json(self.definitions / f'{batch_id}.json', batch)
            return {**run, 'batch': batch}

    def activate(self, batch_id):
        with self.service.write_lock:
            batch = self._load(batch_id)
            self._validate(batch['task_ids'], batch['dependencies'])
            session = self.service._session_payload()
            branch = self.service._git_current_branch(self.repo)
            session['active_batch_id'] = batch_id
            session['active_task_id'] = None
            if branch:
                session.setdefault('active_batches_by_branch', {})[branch] = batch_id
                session.setdefault('active_tasks_by_branch', {}).pop(branch, None)
            session['last_repo_root'] = str(self.repo)
            session['updated_at'] = utc_now()
            self.service.states.save_session(session)
            return {'ok': True, 'batch': batch, 'active_batch': batch, 'session': session, 'errors': []}

    def active(self):
        session = self.service.states.load_session()
        branch = self.service._git_current_branch(self.repo)
        batch_id = session.get('active_batches_by_branch', {}).get(branch) if branch else session.get('active_batch_id')
        batch = self._load(batch_id) if batch_id else None
        return {'ok': True, 'batch': batch, 'active_batch': batch, 'errors': []}

    def create_tasks(self, items):
        with self.service.write_lock:
            if not isinstance(items, list) or not items:
                raise ValidationError('task creation requires a nonempty JSON list')
            signature = inspect.signature(self.service.create_task)
            for item in items:
                if not isinstance(item, dict):
                    raise ValidationError('each task must be an object')
                try:
                    signature.bind(**item)
                except TypeError as exc:
                    raise ValidationError(str(exc)) from exc
                for field in ('title', 'spec_ref'):
                    if not isinstance(item.get(field), str) or not item[field].strip():
                        raise ValidationError(f'{field} must be a nonempty string')
                if item.get('verification_mode', 'manual') not in ('manual', 'self-test'):
                    raise ValidationError('verification_mode must be manual or self-test')
                for field in ('summary', 'plan_node_id', 'parent_task_id', 'source_task_id', 'source_finding_id'):
                    if item.get(field) is not None and not isinstance(item[field], str):
                        raise ValidationError(f'{field} must be a string')
                for field in ('test_commands', 'required_doc_refs', 'required_artifacts', 'owned_paths'):
                    values = item.get(field)
                    if values is not None and (not isinstance(values, list) or not all(isinstance(v, str) and v.strip() for v in values)):
                        raise ValidationError(f'{field} must be a list of nonempty strings')
                for scope in item.get('owned_paths') or []:
                    self.service._normalize_owned_path(scope, self.repo)
                spec = Path(self.service._normalize_repo_path(item['spec_ref'], self.repo))
                if spec.exists():
                    try:
                        spec.read_text(encoding='utf-8')
                    except (OSError, UnicodeError) as exc:
                        raise ValidationError(f'spec is not readable UTF-8: {spec}') from exc
            results = []
            for index, item in enumerate(items):
                try:
                    task = self.service.create_task(**item)['task']
                    results.append({'task_id': task['task_id'], 'title': task['title'], 'status': task['status'], 'ok': True, 'errors': []})
                except (DoneGateMcpError, OSError) as exc:
                    results.append({'input_index': index, 'ok': False, 'errors': [str(exc)]})
            errors = [error for row in results for error in row['errors']]
            return {'ok': not errors, 'tasks': results, 'created_count': sum(row['ok'] for row in results), 'errors': errors}
