"""Resolve a target without inheriting state from another call or server CWD."""
from __future__ import annotations

import json
import os
from pathlib import Path

from donegate_mcp.errors import ValidationError


def absolute_root(value: str | Path, label: str) -> Path:
    path = Path(value).expanduser()
    if not path.is_absolute():
        raise ValidationError(f'{label} must be an absolute path')
    return path.resolve()


def validate_project_owner(data_root: Path, repo_root: Path | None) -> Path | None:
    if data_root.exists() and not data_root.is_dir():
        raise ValidationError(f'data_root is not a directory: {data_root}')
    project_file = data_root / 'project.json'
    if not project_file.exists():
        return repo_root
    try:
        project = json.loads(project_file.read_text(encoding='utf-8'))
        stored = project.get('repo_root')
        owner = absolute_root(stored, 'project.repo_root') if stored else None
    except (ValueError, TypeError, AttributeError, OSError) as exc:
        raise ValidationError(f'invalid project identity at {project_file}: {exc}') from exc
    if repo_root is not None and owner != repo_root:
        raise ValidationError(f'project ownership mismatch: requested {repo_root}, stored {owner} at {data_root}')
    return owner or repo_root


def resolve_mcp_context(repo_root: str | None, data_root: str | None, default_data_root: str | None) -> tuple[Path, Path | None]:
    if repo_root is not None:
        repo = absolute_root(repo_root, 'repo_root')
        data = absolute_root(data_root, 'data_root') if data_root is not None else repo / '.donegate-mcp'
    elif data_root is not None:
        repo = None
        data = absolute_root(data_root, 'data_root')
    else:
        bound_repo = os.environ.get('DONEGATE_MCP_REPO_ROOT') or os.environ.get('DONEGATE_MCP_WORKDIR')
        bound_data = os.environ.get('DONEGATE_MCP_ROOT') or os.environ.get('DONEGATE_MCP_DATA_ROOT')
        repo = absolute_root(bound_repo, 'configured repo_root') if bound_repo else None
        if bound_data:
            data = absolute_root(bound_data, 'configured data_root')
        elif repo is not None:
            data = repo / '.donegate-mcp'
        elif default_data_root:
            data = absolute_root(default_data_root, 'configured data_root')
        else:
            raise ValidationError('target required: pass an absolute repo_root or data_root, or configure a per-project binding')
    if repo is not None and not repo.is_dir():
        raise ValidationError(f'repo_root is not a directory: {repo}')
    repo = validate_project_owner(data, repo)
    return data, repo
