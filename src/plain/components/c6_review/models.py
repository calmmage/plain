from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any


class ReviewStatus(str, Enum):
    READY = "ready"
    IN_REVIEW = "in_review"
    CHANGES_REQUESTED = "changes_requested"
    APPROVED = "approved"
    REJECTED = "rejected"


class FeedbackVerdict(str, Enum):
    APPROVE = "approve"
    REQUEST_CHANGES = "request_changes"
    QUESTION = "question"
    REJECT = "reject"


@dataclass(slots=True)
class ReviewInstruction:
    title: str
    command: str
    cwd: str
    expected_result: str | None = None

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "ReviewInstruction":
        return cls(
            title=str(data.get("title", "")),
            command=str(data.get("command", "")),
            cwd=str(data.get("cwd", "")),
            expected_result=_as_optional_str(data.get("expected_result")),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "title": self.title,
            "command": self.command,
            "cwd": self.cwd,
            "expected_result": self.expected_result,
        }


@dataclass(slots=True)
class ReviewItem:
    review_id: str
    project_id: str
    feature_id: str
    task_key: str | None
    original_vision: str
    summary: str
    status: ReviewStatus = ReviewStatus.READY
    run_instructions: list[ReviewInstruction] = field(default_factory=list)
    changed_files: list[str] = field(default_factory=list)
    source_refs: list[str] = field(default_factory=list)
    conversation_refs: list[str] = field(default_factory=list)
    created_at: datetime = field(default_factory=lambda: utc_now())
    updated_at: datetime = field(default_factory=lambda: utc_now())

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "ReviewItem":
        return cls(
            review_id=str(data.get("review_id", "")),
            project_id=str(data.get("project_id", "")),
            feature_id=str(data.get("feature_id", "")),
            task_key=_as_optional_str(data.get("task_key")),
            original_vision=str(data.get("original_vision", "")),
            summary=str(data.get("summary", "")),
            status=ReviewStatus(str(data.get("status", ReviewStatus.READY.value))),
            run_instructions=[
                ReviewInstruction.from_dict(item)
                for item in data.get("run_instructions", [])
                if isinstance(item, dict)
            ],
            changed_files=_as_str_list(data.get("changed_files")),
            source_refs=_as_str_list(data.get("source_refs")),
            conversation_refs=_as_str_list(data.get("conversation_refs")),
            created_at=parse_datetime(data.get("created_at")),
            updated_at=parse_datetime(data.get("updated_at")),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "review_id": self.review_id,
            "project_id": self.project_id,
            "feature_id": self.feature_id,
            "task_key": self.task_key,
            "original_vision": self.original_vision,
            "summary": self.summary,
            "status": self.status.value,
            "run_instructions": [item.to_dict() for item in self.run_instructions],
            "changed_files": self.changed_files,
            "source_refs": self.source_refs,
            "conversation_refs": self.conversation_refs,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
        }


@dataclass(slots=True)
class FeedbackEntry:
    review_id: str
    author: str = "human"
    verdict: FeedbackVerdict = FeedbackVerdict.QUESTION
    notes: str = ""
    tags: list[str] = field(default_factory=list)
    created_at: datetime = field(default_factory=lambda: utc_now())

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "FeedbackEntry":
        return cls(
            review_id=str(data.get("review_id", "")),
            author=str(data.get("author", "human")),
            verdict=FeedbackVerdict(str(data.get("verdict", FeedbackVerdict.QUESTION.value))),
            notes=str(data.get("notes", "")),
            tags=_as_str_list(data.get("tags")),
            created_at=parse_datetime(data.get("created_at")),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "review_id": self.review_id,
            "author": self.author,
            "verdict": self.verdict.value,
            "notes": self.notes,
            "tags": self.tags,
            "created_at": self.created_at.isoformat(),
        }


@dataclass(slots=True)
class ReviewIngestResult:
    packets_scanned: int
    items_created: int
    items_updated: int
    blocked_items: int


def utc_now() -> datetime:
    return datetime.now(timezone.utc).replace(microsecond=0)


def parse_datetime(value: Any) -> datetime:
    if isinstance(value, datetime):
        return value
    if not value:
        return utc_now()
    return datetime.fromisoformat(str(value))


def _as_optional_str(value: Any) -> str | None:
    if value in (None, ""):
        return None
    return str(value)


def _as_str_list(value: Any) -> list[str]:
    if not value:
        return []
    if isinstance(value, list):
        return [str(item) for item in value]
    return [str(value)]
