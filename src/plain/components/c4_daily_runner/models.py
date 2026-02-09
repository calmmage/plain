from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any


class WorkspaceType(str, Enum):
    MAIN_REPO = "main_repo"
    GIT_WORKTREE = "git_worktree"
    NEW_REPO_FROM_TEMPLATE = "new_repo_from_template"


class ContentOrigin(str, Enum):
    HUMAN = "human"
    AI = "ai"
    MIXED = "mixed"
    UNKNOWN = "unknown"


class JobStatus(str, Enum):
    COMPLETED = "completed"
    REQUIRES_ATTENTION = "requires_attention"
    FAILED = "failed"


@dataclass(slots=True)
class DailyTask:
    key: str
    title: str
    status: str = "todo"
    simple: bool = False
    blocked: bool = False
    backlog: bool = False
    idea: bool = False
    postponed_until: str | None = None
    risk: str = "medium"
    estimated_minutes: int = 90
    source_path: str = ""
    last_touched_at: datetime | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class CandidateScore:
    task_key: str
    score: float
    reasons: list[str]


@dataclass(slots=True)
class RepoState:
    is_clean: bool
    root_path: str


@dataclass(slots=True)
class ContextItem:
    source_type: str
    source_path: str
    text: str
    metadata: dict[str, Any] = field(default_factory=dict)
    origin: ContentOrigin = ContentOrigin.UNKNOWN


@dataclass(slots=True)
class ContextPacket:
    items: list[ContextItem]
    summary: str
    source_type_counts: dict[str, int]


@dataclass(slots=True)
class DailyJobResult:
    selected_task: str
    workspace_type: WorkspaceType
    workspace_path: str
    client: str
    session_id: str
    changed_files: list[str]
    review_packet: str
    execution_log: str
    status: JobStatus
    score_breakdown: list[CandidateScore] = field(default_factory=list)


@dataclass(slots=True)
class ReviewPacket:
    path: Path
    summary: str
    changed_files: list[str]
    run_instructions: list[str]
    unresolved_questions: list[str]


def utc_now() -> datetime:
    return datetime.now(timezone.utc).replace(microsecond=0)
