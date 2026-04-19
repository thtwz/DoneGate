from __future__ import annotations

from pathlib import Path
from typing import Any

from donegate_mcp.config import PLAN_FILENAME, PROGRESS_FILENAME
from donegate_mcp.storage.fs import atomic_write_json, read_json


class StateStore:
    def __init__(self, data_root: Path) -> None:
        self.plan_path = data_root / PLAN_FILENAME
        self.progress_path = data_root / PROGRESS_FILENAME

    def load_plan(self) -> dict[str, Any]:
        return read_json(self.plan_path)

    def save_plan(self, data: dict[str, Any]) -> dict[str, Any]:
        atomic_write_json(self.plan_path, data)
        return data

    def load_progress(self) -> dict[str, Any]:
        return read_json(self.progress_path)

    def save_progress(self, data: dict[str, Any]) -> dict[str, Any]:
        atomic_write_json(self.progress_path, data)
        return data

    def plan_exists(self) -> bool:
        return self.plan_path.exists()

    def progress_exists(self) -> bool:
        return self.progress_path.exists()
