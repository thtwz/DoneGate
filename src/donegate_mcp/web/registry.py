"""User-local workspace index; task data stays in each workspace."""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
from typing import Any

from donegate_mcp.context import absolute_root, validate_project_owner
from donegate_mcp.errors import ValidationError
from donegate_mcp.storage.fs import atomic_write_json, read_json
from donegate_mcp.storage.workspace_lock import WorkspaceWriteLock


def default_registry() -> Path:
    base = Path(os.environ.get("XDG_CONFIG_HOME", str(Path.home() / ".config")))
    return base / "donegate" / "projects.json"


def validate_entry(entry: dict[str, Any]) -> dict[str, Any]:
    repo = absolute_root(entry["repo_root"], "repo_root")
    data = absolute_root(entry["data_root"], "data_root")
    if not repo.is_dir() or not (data / "project.json").is_file():
        raise ValidationError(f"项目不存在或未初始化 DoneGate：{repo}")
    validate_project_owner(data, repo)
    project = read_json(data / "project.json")
    if not isinstance(project, dict) or any(not isinstance(project.get(key), str) or not project[key].strip()
                                            for key in ("project_id", "project_name")):
        raise ValidationError("项目标识无效")
    if entry.get("project_id") and entry["project_id"] != project["project_id"]:
        raise ValidationError("项目标识已变化，请移除后重新添加该工作区")
    return {**entry, "project_id": project["project_id"], "project_name": project["project_name"],
            "repo_root": str(repo), "data_root": str(data)}


class ProjectRegistry:
    def __init__(self, path: Path | None = None) -> None:
        self.path = (path or default_registry()).expanduser().resolve()
        self.lock = WorkspaceWriteLock(self.path.with_suffix(".lock"))

    def list(self) -> list[dict[str, Any]]:
        if not self.path.exists():
            return []
        try:
            payload = read_json(self.path)
            rows = payload["projects"]
            if not isinstance(rows, list) or any(not isinstance(row, dict) for row in rows):
                raise ValueError("invalid projects")
            for row in rows:
                if any(not isinstance(row.get(k), str) for k in ("key", "repo_root", "data_root", "project_id", "project_name")):
                    raise ValueError("invalid project entry")
            return rows
        except (KeyError, TypeError, ValueError) as exc:
            raise ValidationError(f"项目索引损坏：{self.path}") from exc

    def get(self, key: str) -> dict[str, Any]:
        for row in self.list():
            if row["key"] == key:
                return row
        raise KeyError(key)

    def add(self, repo_root: str, data_root: str | None = None) -> dict[str, Any]:
        repo = absolute_root(repo_root, "repo_root")
        data = absolute_root(data_root, "data_root") if data_root else repo / ".donegate-mcp"
        entry = validate_entry({"repo_root": str(repo), "data_root": str(data)})
        identity = json.dumps([entry["repo_root"], entry["data_root"], entry["project_id"]])
        entry["key"] = hashlib.sha256(identity.encode()).hexdigest()[:24]
        with self.lock:
            rows = self.list()
            for row in rows:
                if row["key"] == entry["key"]:
                    return row
            atomic_write_json(self.path, {"projects": [*rows, entry]})
        return entry

    def remove(self, key: str) -> None:
        with self.lock:
            rows = self.list()
            if not any(row["key"] == key for row in rows):
                raise KeyError(key)
            atomic_write_json(self.path, {"projects": [row for row in rows if row["key"] != key]})
