from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


class TaskStatus(str, Enum):
    DRAFT = "draft"
    READY = "ready"
    IN_PROGRESS = "in_progress"
    AWAITING_VERIFICATION = "awaiting_verification"
    VERIFIED = "verified"
    DOCUMENTED = "documented"
    DONE = "done"
    BLOCKED = "blocked"


class VerificationStatus(str, Enum):
    UNKNOWN = "unknown"
    FAILED = "failed"
    PASSED = "passed"


class DocSyncStatus(str, Enum):
    UNKNOWN = "unknown"
    OUTDATED = "outdated"
    SYNCED = "synced"


@dataclass(slots=True)
class ProjectState:
    schema_version: int
    project_id: str
    project_name: str
    created_at: str
    updated_at: str
    default_branch: str | None = None
    task_counter: int = 0

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "ProjectState":
        return cls(**data)


@dataclass(slots=True)
class Task:
    task_id: str
    title: str
    spec_ref: str
    status: TaskStatus
    summary: str = ""
    blocked_reason: str | None = None
    created_at: str = field(default_factory=utc_now)
    updated_at: str = field(default_factory=utc_now)
    started_at: str | None = None
    verified_at: str | None = None
    documented_at: str | None = None
    done_at: str | None = None
    verification_status: VerificationStatus = VerificationStatus.UNKNOWN
    doc_sync_status: DocSyncStatus = DocSyncStatus.UNKNOWN
    last_verification_ref: str | None = None
    last_doc_sync_ref: str | None = None
    verification_mode: str = "manual"
    test_commands: list[str] = field(default_factory=list)
    required_doc_refs: list[str] = field(default_factory=list)
    required_artifacts: list[str] = field(default_factory=list)
    last_self_test_at: str | None = None
    last_self_test_exit_code: int | None = None
    last_self_test_ref: str | None = None
    plan_node_id: str | None = None
    spec_version: int | None = None
    spec_hash: str | None = None
    stale_reason: str | None = None
    needs_revalidation: bool = False

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["status"] = self.status.value
        data["verification_status"] = self.verification_status.value
        data["doc_sync_status"] = self.doc_sync_status.value
        data["projected_status"] = self.status.value
        data["status_source"] = "projected"
        return data

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Task":
        payload = dict(data)
        payload["status"] = TaskStatus(payload["status"])
        payload["verification_status"] = VerificationStatus(payload["verification_status"])
        payload["doc_sync_status"] = DocSyncStatus(payload["doc_sync_status"])
        payload.setdefault("verification_mode", "manual")
        payload.setdefault("test_commands", [])
        payload.setdefault("required_doc_refs", [])
        payload.setdefault("required_artifacts", [])
        payload.setdefault("last_self_test_at", None)
        payload.setdefault("last_self_test_exit_code", None)
        payload.setdefault("last_self_test_ref", None)
        payload.setdefault("plan_node_id", None)
        payload.setdefault("spec_version", None)
        payload.setdefault("spec_hash", None)
        payload.setdefault("stale_reason", None)
        payload.setdefault("needs_revalidation", False)
        payload.pop("projected_status", None)
        payload.pop("status_source", None)
        return cls(**payload)


@dataclass(slots=True)
class VerificationRecord:
    task_id: str
    result: VerificationStatus
    recorded_at: str
    ref: str | None = None
    notes: str | None = None

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["result"] = self.result.value
        return data


@dataclass(slots=True)
class SelfTestRecord:
    task_id: str
    recorded_at: str
    command_count: int
    exit_code: int
    ref: str | None = None
    stdout_path: str | None = None
    stderr_path: str | None = None
    commands: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class DocSyncRecord:
    task_id: str
    result: DocSyncStatus
    recorded_at: str
    ref: str | None = None
    notes: str | None = None

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["result"] = self.result.value
        return data


@dataclass(slots=True)
class TaskEvent:
    type: str
    timestamp: str
    actor: str
    payload: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class DashboardSummary:
    project_name: str
    total_tasks: int
    counts_by_status: dict[str, int]
    blocked_tasks: list[dict[str, Any]]
    missing_verification: list[dict[str, Any]]
    missing_docs: list[dict[str, Any]]
    next_actions: list[dict[str, Any]]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)
