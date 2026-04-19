from __future__ import annotations

from pathlib import Path

from delivery_mcp.config import EVENTS_DIRNAME
from delivery_mcp.models import TaskEvent
from delivery_mcp.storage.fs import append_jsonl, ensure_dir


class EventStore:
    def __init__(self, data_root: Path) -> None:
        self.events_dir = ensure_dir(data_root / EVENTS_DIRNAME)

    def append(self, task_id: str, event: TaskEvent) -> TaskEvent:
        append_jsonl(self.events_dir / f"{task_id}.jsonl", event.to_dict())
        return event
