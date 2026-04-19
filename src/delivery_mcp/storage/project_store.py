from __future__ import annotations

from pathlib import Path

from delivery_mcp.config import PROJECT_FILENAME
from delivery_mcp.models import ProjectState
from delivery_mcp.storage.fs import atomic_write_json, read_json


class ProjectStore:
    def __init__(self, data_root: Path) -> None:
        self.data_root = data_root
        self.path = data_root / PROJECT_FILENAME

    def exists(self) -> bool:
        return self.path.exists()

    def load(self) -> ProjectState:
        return ProjectState.from_dict(read_json(self.path))

    def save(self, project: ProjectState) -> ProjectState:
        atomic_write_json(self.path, project.to_dict())
        return project
