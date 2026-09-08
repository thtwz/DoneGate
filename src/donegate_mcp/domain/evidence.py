"""Content snapshots for verification and advisory reuse in Git workspaces."""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import subprocess

from donegate_mcp.errors import ValidationError
from donegate_mcp.models import Task


def _matches(path: str, scope: str) -> bool:
    if scope in ("", "."):
        return True
    if any(char in scope for char in '*?[]'):
        return PurePosixPath(path).match(scope)
    return path == scope or path.startswith(scope.rstrip('/') + '/')


def input_snapshot(task: Task, repo: Path, data_root: Path) -> str | None:
    """Hash scoped working-tree inputs, independent of staging/commit timestamps.

    Non-Git projects retain manual verification semantics. Declared artifacts and
    DoneGate state are outputs, not test inputs. Missing/deleted inputs still affect
    the digest. Git ignored, untracked build products are not scanned.
    """
    git_root = subprocess.run(['git', '-C', str(repo), 'rev-parse', '--show-toplevel'], capture_output=True, text=True)
    if git_root.returncode != 0:
        return None
    if Path(git_root.stdout.strip()).resolve() != repo.resolve():
        raise ValidationError('verification repo_root must be the Git worktree root')
    listing = subprocess.run(['git', '-C', str(repo), 'ls-files', '-z', '--cached', '--others', '--exclude-standard'], capture_output=True)
    if listing.returncode:
        raise ValidationError('unable to enumerate verification inputs')
    paths = set(os.fsdecode(value) for value in listing.stdout.split(b'\0') if value)
    selected = {repo / path for path in paths if not task.owned_paths or any(_matches(path, scope) for scope in task.owned_paths)}
    selected.update(Path(path) for path in [task.spec_ref, *task.required_doc_refs])
    outputs = [Path(path).absolute() for path in task.required_artifacts]
    state = data_root.resolve()
    digest = hashlib.sha256()
    protocol = {'mode': task.verification_mode, 'commands': task.test_commands,
                'scope': task.owned_paths, 'docs': task.required_doc_refs,
                'artifacts': task.required_artifacts, 'spec': task.spec_ref}
    digest.update(json.dumps(protocol, sort_keys=True).encode())
    for path in sorted(selected, key=str):
        path = path.absolute()
        if path == state or state in path.parents or any(path == output or output in path.parents for output in outputs):
            continue
        try:
            relative = path.relative_to(repo).as_posix()
        except ValueError:
            relative = str(path)
        if any(part.startswith('.donegate-mcp') for part in Path(relative).parts):
            continue
        digest.update(relative.encode(errors='surrogateescape') + b'\0')
        try:
            if path.is_symlink():
                digest.update(b'link:' + os.fsencode(os.readlink(path)))
            elif path.is_file():
                digest.update(b'executable:' + str(bool(path.stat().st_mode & 0o111)).encode())
                with path.open('rb') as stream:
                    for chunk in iter(lambda: stream.read(65536), b''):
                        digest.update(chunk)
            elif path.is_dir():
                # Gitlinks: include their revision and diff; regular source trees
                # have their files enumerated separately by git ls-files.
                head = subprocess.run(['git', '-C', str(path), 'rev-parse', 'HEAD'], capture_output=True)
                diff = subprocess.run(['git', '-C', str(path), 'diff', 'HEAD', '--binary'], capture_output=True)
                digest.update(b'directory:' + head.stdout + diff.stdout)
            else:
                digest.update(b'missing')
        except OSError as exc:
            raise ValidationError(f'unable to read verification input: {path}') from exc
        digest.update(b'\0')
    return digest.hexdigest()
