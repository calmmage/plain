from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any

from plain.core.models import FlowError


class PrincipleStatus(str, Enum):
    DRAFT = "draft"
    APPROVED = "approved"
    REJECTED = "rejected"


class SkillCandidateStatus(str, Enum):
    DRAFT = "draft"
    REVIEW = "review"
    APPROVED = "approved"
    REJECTED = "rejected"


class SkillTargetScope(str, Enum):
    CODING = "coding"
    RELEASE = "release"
    REVIEW = "review"
    UX = "ux"


@dataclass(slots=True)
class PrincipleNote:
    principle_id: str
    title: str
    raw_quote: str
    normalized_rule: str
    rationale: str
    source_path: str
    source_session_id: str | None = None
    tags: list[str] = field(default_factory=list)
    example_good: str | None = None
    example_bad: str | None = None
    status: PrincipleStatus = PrincipleStatus.DRAFT
    created_at: datetime = field(default_factory=lambda: utc_now())
    updated_at: datetime = field(default_factory=lambda: utc_now())

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "PrincipleNote":
        try:
            status = PrincipleStatus(str(data.get("status", PrincipleStatus.DRAFT.value)))
        except ValueError as exc:
            raise FlowError(f"Invalid principle status: {data.get('status')}") from exc

        return cls(
            principle_id=str(data.get("principle_id", "")).strip(),
            title=str(data.get("title", "")).strip(),
            raw_quote=str(data.get("raw_quote", "")).strip(),
            normalized_rule=str(data.get("normalized_rule", "")).strip(),
            rationale=str(data.get("rationale", "")).strip(),
            source_path=str(data.get("source_path", "")).strip(),
            source_session_id=_as_optional_str(data.get("source_session_id")),
            tags=_as_str_list(data.get("tags")),
            example_good=_as_optional_str(data.get("example_good")),
            example_bad=_as_optional_str(data.get("example_bad")),
            status=status,
            created_at=parse_datetime(data.get("created_at")),
            updated_at=parse_datetime(data.get("updated_at")),
        )

    def validate(self) -> None:
        if not self.principle_id:
            raise FlowError("principle_id is required")
        if not self.title:
            raise FlowError("title is required")
        if not self.raw_quote:
            raise FlowError("raw_quote is required")
        if not self.normalized_rule:
            raise FlowError("normalized_rule is required")
        if not self.rationale:
            raise FlowError("rationale is required")
        if not self.source_path:
            raise FlowError("source_path is required")

    def to_dict(self) -> dict[str, Any]:
        return {
            "principle_id": self.principle_id,
            "title": self.title,
            "raw_quote": self.raw_quote,
            "normalized_rule": self.normalized_rule,
            "rationale": self.rationale,
            "source_path": self.source_path,
            "source_session_id": self.source_session_id,
            "tags": self.tags,
            "example_good": self.example_good,
            "example_bad": self.example_bad,
            "status": self.status.value,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
        }


@dataclass(slots=True)
class SkillCandidate:
    candidate_id: str
    name: str
    principle_ids: list[str]
    target_scope: SkillTargetScope
    status: SkillCandidateStatus = SkillCandidateStatus.DRAFT
    skill_path: str | None = None
    test_prompt: str | None = None
    last_test_score: int | None = None
    last_test_notes: str | None = None
    created_at: datetime = field(default_factory=lambda: utc_now())
    updated_at: datetime = field(default_factory=lambda: utc_now())

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "SkillCandidate":
        try:
            target_scope = SkillTargetScope(
                str(data.get("target_scope", SkillTargetScope.CODING.value))
            )
        except ValueError as exc:
            raise FlowError(f"Invalid candidate scope: {data.get('target_scope')}") from exc

        try:
            status = SkillCandidateStatus(
                str(data.get("status", SkillCandidateStatus.DRAFT.value))
            )
        except ValueError as exc:
            raise FlowError(f"Invalid candidate status: {data.get('status')}") from exc

        return cls(
            candidate_id=str(data.get("candidate_id", "")).strip(),
            name=str(data.get("name", "")).strip(),
            principle_ids=_as_str_list(data.get("principle_ids")),
            target_scope=target_scope,
            status=status,
            skill_path=_as_optional_str(data.get("skill_path")),
            test_prompt=_as_optional_str(data.get("test_prompt")),
            last_test_score=_as_optional_int(data.get("last_test_score")),
            last_test_notes=_as_optional_str(data.get("last_test_notes")),
            created_at=parse_datetime(data.get("created_at")),
            updated_at=parse_datetime(data.get("updated_at")),
        )

    def validate(self) -> None:
        if not self.candidate_id:
            raise FlowError("candidate_id is required")
        if not self.name:
            raise FlowError("name is required")
        if not self.principle_ids:
            raise FlowError("principle_ids must include at least one principle")

    def to_dict(self) -> dict[str, Any]:
        return {
            "candidate_id": self.candidate_id,
            "name": self.name,
            "principle_ids": self.principle_ids,
            "target_scope": self.target_scope.value,
            "status": self.status.value,
            "skill_path": self.skill_path,
            "test_prompt": self.test_prompt,
            "last_test_score": self.last_test_score,
            "last_test_notes": self.last_test_notes,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
        }


@dataclass(slots=True)
class SkillTestResult:
    candidate_id: str
    score: int
    notes: list[str]
    passed: bool


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


def _as_optional_int(value: Any) -> int | None:
    if value in (None, ""):
        return None
    try:
        return int(value)
    except Exception:
        return None
