from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from donegate_mcp.errors import ValidationError
from donegate_mcp.models import ReviewCheckpoint, ReviewRecommendation, Task


@dataclass(slots=True)
class NormalizedReviewInput:
    summary: str
    overall_recommendation: str
    findings: list[dict]


class ReviewProvider(Protocol):
    provider_id: str

    def build_request_hint(self, task: Task, checkpoint: ReviewCheckpoint) -> str: ...

    def normalize_input(
        self,
        task: Task,
        checkpoint: ReviewCheckpoint,
        summary: str,
        overall_recommendation: str,
        findings: list[dict] | None,
    ) -> NormalizedReviewInput: ...


class ManualReviewProvider:
    provider_id = "manual"

    def build_request_hint(self, task: Task, checkpoint: ReviewCheckpoint) -> str:
        return f"Record a manual advisory review for {task.task_id} at {checkpoint.value}."

    def normalize_input(
        self,
        task: Task,
        checkpoint: ReviewCheckpoint,
        summary: str,
        overall_recommendation: str,
        findings: list[dict] | None,
    ) -> NormalizedReviewInput:
        findings = list(findings or [])
        if not summary and not findings:
            raise ValidationError("manual review requires a summary or at least one finding")
        return NormalizedReviewInput(
            summary=summary,
            overall_recommendation=overall_recommendation or ReviewRecommendation.PROCEED.value,
            findings=findings,
        )


class HostSkillReviewProvider:
    provider_id = "host_skill"

    def build_request_hint(self, task: Task, checkpoint: ReviewCheckpoint) -> str:
        owned_paths = ", ".join(task.owned_paths) if task.owned_paths else "no declared owned paths"
        return (
            f"Run an architect-style advisory review for task {task.task_id} at checkpoint {checkpoint.value}. "
            f"Focus on whether the implementation solves the real user need, not only the literal acceptance path. "
            f"Spec: {task.spec_ref}. Owned paths: {owned_paths}. "
            f"If you find a value gap, propose a follow-up task."
        )

    def normalize_input(
        self,
        task: Task,
        checkpoint: ReviewCheckpoint,
        summary: str,
        overall_recommendation: str,
        findings: list[dict] | None,
    ) -> NormalizedReviewInput:
        findings = list(findings or [])
        if not summary and not findings:
            raise ValidationError("host_skill review requires a summary or at least one finding")
        return NormalizedReviewInput(
            summary=summary,
            overall_recommendation=overall_recommendation or ReviewRecommendation.NEEDS_HUMAN_ATTENTION.value,
            findings=findings,
        )


_PROVIDERS: dict[str, ReviewProvider] = {
    ManualReviewProvider.provider_id: ManualReviewProvider(),
    HostSkillReviewProvider.provider_id: HostSkillReviewProvider(),
}


def get_review_provider(provider_id: str) -> ReviewProvider:
    try:
        return _PROVIDERS[provider_id]
    except KeyError as exc:
        raise ValidationError(f"unknown review provider: {provider_id}") from exc
