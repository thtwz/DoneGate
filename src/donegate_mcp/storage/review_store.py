from __future__ import annotations

from pathlib import Path

from donegate_mcp.config import REVIEW_FINDINGS_DIRNAME, REVIEW_RUNS_DIRNAME
from donegate_mcp.models import ReviewFinding, ReviewRun
from donegate_mcp.storage.fs import atomic_write_json, ensure_dir, read_json


class ReviewRunStore:
    def __init__(self, data_root: Path) -> None:
        self.review_runs_dir = ensure_dir(data_root / REVIEW_RUNS_DIRNAME)

    def path_for(self, review_run_id: str) -> Path:
        return self.review_runs_dir / f"{review_run_id}.json"

    def load(self, review_run_id: str) -> ReviewRun:
        return ReviewRun.from_dict(read_json(self.path_for(review_run_id)))

    def save(self, review_run: ReviewRun) -> ReviewRun:
        atomic_write_json(self.path_for(review_run.review_run_id), review_run.to_dict())
        return review_run

    def list(self) -> list[ReviewRun]:
        return [ReviewRun.from_dict(read_json(path)) for path in sorted(self.review_runs_dir.glob("REVIEW-*.json"))]


class ReviewFindingStore:
    def __init__(self, data_root: Path) -> None:
        self.review_findings_dir = ensure_dir(data_root / REVIEW_FINDINGS_DIRNAME)

    def path_for(self, finding_id: str) -> Path:
        return self.review_findings_dir / f"{finding_id}.json"

    def load(self, finding_id: str) -> ReviewFinding:
        return ReviewFinding.from_dict(read_json(self.path_for(finding_id)))

    def save(self, finding: ReviewFinding) -> ReviewFinding:
        atomic_write_json(self.path_for(finding.finding_id), finding.to_dict())
        return finding

    def list(self) -> list[ReviewFinding]:
        return [ReviewFinding.from_dict(read_json(path)) for path in sorted(self.review_findings_dir.glob("FINDING-*.json"))]
