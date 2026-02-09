from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any


class Phase(str, Enum):
    MAKE_IT_WORK = "make_it_work"
    TEST = "test"
    POLISH = "polish"


class PhaseStatus(str, Enum):
    TODO = "todo"
    ACTIVE = "active"
    BLOCKED = "blocked"
    DONE = "done"


PHASE_ORDER: tuple[Phase, ...] = (
    Phase.MAKE_IT_WORK,
    Phase.TEST,
    Phase.POLISH,
)


class FlowError(ValueError):
    """Domain error for invalid flow state operations."""


@dataclass(slots=True)
class ArtifactRef:
    kind: str
    path: str
    note: str | None = None

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "ArtifactRef":
        return cls(
            kind=str(data.get("kind", "")),
            path=str(data.get("path", "")),
            note=_as_optional_str(data.get("note")),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "kind": self.kind,
            "path": self.path,
            "note": self.note,
        }


@dataclass(slots=True)
class ConversationRef:
    client: str
    session_id: str
    cwd: str
    summary: str | None = None
    linked_at: datetime = field(default_factory=lambda: utc_now())

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "ConversationRef":
        return cls(
            client=str(data.get("client", "")),
            session_id=str(data.get("session_id", "")),
            cwd=str(data.get("cwd", "")),
            summary=_as_optional_str(data.get("summary")),
            linked_at=parse_datetime(data.get("linked_at")),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "client": self.client,
            "session_id": self.session_id,
            "cwd": self.cwd,
            "summary": self.summary,
            "linked_at": self.linked_at.isoformat(),
        }


@dataclass(slots=True)
class PhaseRecord:
    phase: Phase
    status: PhaseStatus = PhaseStatus.TODO
    started_at: datetime | None = None
    finished_at: datetime | None = None
    owner: str = "human+ai"
    entry_criteria: list[str] = field(default_factory=list)
    exit_criteria: list[str] = field(default_factory=list)
    artifacts: list[ArtifactRef] = field(default_factory=list)
    conversations: list[ConversationRef] = field(default_factory=list)
    feedback: list[str] = field(default_factory=list)
    blockers: list[str] = field(default_factory=list)

    # Structured metadata per phase status.
    code_links: list[str] = field(default_factory=list)
    entry_points: list[str] = field(default_factory=list)
    explanations: list[str] = field(default_factory=list)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "PhaseRecord":
        return cls(
            phase=Phase(str(data.get("phase", Phase.MAKE_IT_WORK.value))),
            status=PhaseStatus(str(data.get("status", PhaseStatus.TODO.value))),
            started_at=parse_datetime_or_none(data.get("started_at")),
            finished_at=parse_datetime_or_none(data.get("finished_at")),
            owner=str(data.get("owner", "human+ai")),
            entry_criteria=_as_str_list(data.get("entry_criteria")),
            exit_criteria=_as_str_list(data.get("exit_criteria")),
            artifacts=[ArtifactRef.from_dict(x) for x in _as_dict_list(data.get("artifacts"))],
            conversations=[
                ConversationRef.from_dict(x) for x in _as_dict_list(data.get("conversations"))
            ],
            feedback=_as_str_list(data.get("feedback")),
            blockers=_as_str_list(data.get("blockers")),
            code_links=_as_str_list(data.get("code_links")),
            entry_points=_as_str_list(data.get("entry_points")),
            explanations=_as_str_list(data.get("explanations")),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "phase": self.phase.value,
            "status": self.status.value,
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "finished_at": self.finished_at.isoformat() if self.finished_at else None,
            "owner": self.owner,
            "entry_criteria": self.entry_criteria,
            "exit_criteria": self.exit_criteria,
            "artifacts": [item.to_dict() for item in self.artifacts],
            "conversations": [item.to_dict() for item in self.conversations],
            "feedback": self.feedback,
            "blockers": self.blockers,
            "code_links": self.code_links,
            "entry_points": self.entry_points,
            "explanations": self.explanations,
        }


@dataclass(slots=True)
class FeatureFlow:
    feature_id: str
    title: str
    vision: str
    current_phase: Phase = Phase.MAKE_IT_WORK
    phases: list[PhaseRecord] = field(default_factory=list)
    created_at: datetime = field(default_factory=lambda: utc_now())
    updated_at: datetime = field(default_factory=lambda: utc_now())
    completed_at: datetime | None = None

    @classmethod
    def create(cls, feature_id: str, title: str, vision: str) -> "FeatureFlow":
        return cls(
            feature_id=feature_id,
            title=title,
            vision=vision,
            phases=[PhaseRecord(phase=phase) for phase in PHASE_ORDER],
        )

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "FeatureFlow":
        feature = cls(
            feature_id=str(data.get("feature_id", "")),
            title=str(data.get("title", "")),
            vision=str(data.get("vision", "")),
            current_phase=Phase(str(data.get("current_phase", Phase.MAKE_IT_WORK.value))),
            phases=[PhaseRecord.from_dict(x) for x in _as_dict_list(data.get("phases"))],
            created_at=parse_datetime(data.get("created_at")),
            updated_at=parse_datetime(data.get("updated_at")),
            completed_at=parse_datetime_or_none(data.get("completed_at")),
        )
        feature._ensure_all_phase_records()
        return feature

    def _ensure_all_phase_records(self) -> None:
        by_phase = {record.phase: record for record in self.phases}
        self.phases = [by_phase.get(phase, PhaseRecord(phase=phase)) for phase in PHASE_ORDER]

    def get_phase_record(self, phase: Phase | None = None) -> PhaseRecord:
        target = phase or self.current_phase
        for record in self.phases:
            if record.phase == target:
                return record
        raise FlowError(f"Missing phase record for {target.value}")

    def to_dict(self) -> dict[str, Any]:
        return {
            "feature_id": self.feature_id,
            "title": self.title,
            "vision": self.vision,
            "current_phase": self.current_phase.value,
            "phases": [phase.to_dict() for phase in self.phases],
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
        }


@dataclass(slots=True)
class ProjectFlow:
    project_id: str
    project_name: str
    repository_path: str
    features: list[FeatureFlow] = field(default_factory=list)
    tags: list[str] = field(default_factory=list)
    created_at: datetime = field(default_factory=lambda: utc_now())
    updated_at: datetime = field(default_factory=lambda: utc_now())

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "ProjectFlow":
        return cls(
            project_id=str(data.get("project_id", "")),
            project_name=str(data.get("project_name", "")),
            repository_path=str(data.get("repository_path", "")),
            features=[FeatureFlow.from_dict(x) for x in _as_dict_list(data.get("features"))],
            tags=_as_str_list(data.get("tags")),
            created_at=parse_datetime(data.get("created_at")),
            updated_at=parse_datetime(data.get("updated_at")),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "project_id": self.project_id,
            "project_name": self.project_name,
            "repository_path": self.repository_path,
            "features": [feature.to_dict() for feature in self.features],
            "tags": self.tags,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
        }

    def get_feature(self, feature_id: str) -> FeatureFlow:
        for feature in self.features:
            if feature.feature_id == feature_id:
                return feature
        raise FlowError(f"Feature not found: {feature_id}")


def utc_now() -> datetime:
    return datetime.now(timezone.utc).replace(microsecond=0)


def parse_datetime(value: Any) -> datetime:
    if isinstance(value, datetime):
        return value
    if not value:
        return utc_now()
    return datetime.fromisoformat(str(value))


def parse_datetime_or_none(value: Any) -> datetime | None:
    if value in (None, "", "null"):
        return None
    return parse_datetime(value)


def _as_optional_str(value: Any) -> str | None:
    if value is None:
        return None
    return str(value)


def _as_str_list(value: Any) -> list[str]:
    if not value:
        return []
    if isinstance(value, list):
        return [str(x) for x in value]
    return [str(value)]


def _as_dict_list(value: Any) -> list[dict[str, Any]]:
    if not value:
        return []
    if isinstance(value, list):
        return [x for x in value if isinstance(x, dict)]
    return []
