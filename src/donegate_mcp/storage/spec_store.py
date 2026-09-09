"""Versioned requirement bodies. Writers hold the workspace write lock."""
from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Any

from donegate_mcp.models import utc_now
from donegate_mcp.storage.fs import atomic_write_json, read_json


class SpecStore:
    def __init__(self, data_root: Path) -> None:
        self.directory = data_root / "spec-history"

    def capture(self, spec_ref: str, content: str, reason: str,
                affected_task_ids: list[str]) -> dict[str, Any]:
        key = hashlib.sha256(spec_ref.encode()).hexdigest()
        path = self.directory / f"{key}.json"
        rows = read_json(path)["revisions"] if path.exists() else []
        digest = hashlib.sha256(content.encode("utf-8")).hexdigest()
        previous = rows[-1] if rows else None
        if previous and previous["spec_hash"] == digest:
            return previous
        row = {
            "id": f"{key}:{len(rows) + 1}", "spec_ref": spec_ref,
            "version": len(rows) + 1, "timestamp": utc_now(),
            "spec_hash": digest, "previous_hash": previous["spec_hash"] if previous else None,
            "reason": reason, "affected_task_ids": list(affected_task_ids), "content": content,
        }
        atomic_write_json(path, {"revisions": [*rows, row]})
        return row

    def list(self) -> list[dict[str, Any]]:
        return [row for path in sorted(self.directory.glob("*.json"))
                for row in read_json(path)["revisions"]]
