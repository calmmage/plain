from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any


class ScenarioKind(str, Enum):
    START = "start"
    FINISH = "finish"


class StepPrimitive(str, Enum):
    SHELL_COMMAND = "shell_command"
    AGENT_PROMPT = "agent_prompt"
    FILE_TEMPLATE_APPLY = "file_template_apply"
    HUMAN_CONFIRMATION = "human_confirmation"
    VALIDATION_CHECK = "validation_check"


class ExecutionMode(str, Enum):
    INTERACTIVE = "interactive"
    OBSERVE = "observe"


class RunStatus(str, Enum):
    RUNNING = "running"
    PAUSED = "paused"
    DONE = "done"
    FAILED = "failed"


@dataclass(slots=True)
class ScenarioStep:
    step_id: str
    title: str
    command: str | None = None
    instruction: str | None = None
    primitive: StepPrimitive = StepPrimitive.SHELL_COMMAND
    requires_human: bool = False
    timeout_sec: int = 600

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "ScenarioStep":
        return cls(
            step_id=str(data.get("step_id", "")),
            title=str(data.get("title", "")),
            command=_as_optional_str(data.get("command")),
            instruction=_as_optional_str(data.get("instruction")),
            primitive=StepPrimitive(
                str(data.get("primitive", StepPrimitive.SHELL_COMMAND.value))
            ),
            requires_human=bool(data.get("requires_human", False)),
            timeout_sec=int(data.get("timeout_sec", 600)),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "step_id": self.step_id,
            "title": self.title,
            "command": self.command,
            "instruction": self.instruction,
            "primitive": self.primitive.value,
            "requires_human": self.requires_human,
            "timeout_sec": self.timeout_sec,
        }


@dataclass(slots=True)
class BootstrapScenario:
    scenario_id: str
    kind: ScenarioKind
    title: str
    description: str
    tags: list[str] = field(default_factory=list)
    steps: list[ScenarioStep] = field(default_factory=list)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "BootstrapScenario":
        return cls(
            scenario_id=str(data.get("scenario_id", "")),
            kind=ScenarioKind(str(data.get("kind", ScenarioKind.START.value))),
            title=str(data.get("title", "")),
            description=str(data.get("description", "")),
            tags=_as_str_list(data.get("tags")),
            steps=[
                ScenarioStep.from_dict(item)
                for item in data.get("steps", [])
                if isinstance(item, dict)
            ],
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "scenario_id": self.scenario_id,
            "kind": self.kind.value,
            "title": self.title,
            "description": self.description,
            "tags": self.tags,
            "steps": [step.to_dict() for step in self.steps],
        }


@dataclass(slots=True)
class StepRunRecord:
    step_id: str
    status: str
    summary: str
    started_at: datetime = field(default_factory=lambda: utc_now())
    finished_at: datetime = field(default_factory=lambda: utc_now())

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "StepRunRecord":
        return cls(
            step_id=str(data.get("step_id", "")),
            status=str(data.get("status", "")),
            summary=str(data.get("summary", "")),
            started_at=parse_datetime(data.get("started_at")),
            finished_at=parse_datetime(data.get("finished_at")),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "step_id": self.step_id,
            "status": self.status,
            "summary": self.summary,
            "started_at": self.started_at.isoformat(),
            "finished_at": self.finished_at.isoformat(),
        }


@dataclass(slots=True)
class ScenarioRun:
    run_id: str
    scenario_id: str
    mode: ExecutionMode
    status: RunStatus
    started_at: datetime
    finished_at: datetime | None = None
    next_step_index: int = 0
    completed_steps: list[str] = field(default_factory=list)
    failed_step: str | None = None
    notes: list[str] = field(default_factory=list)
    changed_files: list[str] = field(default_factory=list)
    step_results: list[StepRunRecord] = field(default_factory=list)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "ScenarioRun":
        return cls(
            run_id=str(data.get("run_id", "")),
            scenario_id=str(data.get("scenario_id", "")),
            mode=ExecutionMode(str(data.get("mode", ExecutionMode.INTERACTIVE.value))),
            status=RunStatus(str(data.get("status", RunStatus.RUNNING.value))),
            started_at=parse_datetime(data.get("started_at")),
            finished_at=parse_datetime_or_none(data.get("finished_at")),
            next_step_index=int(data.get("next_step_index", 0)),
            completed_steps=_as_str_list(data.get("completed_steps")),
            failed_step=_as_optional_str(data.get("failed_step")),
            notes=_as_str_list(data.get("notes")),
            changed_files=_as_str_list(data.get("changed_files")),
            step_results=[
                StepRunRecord.from_dict(item)
                for item in data.get("step_results", [])
                if isinstance(item, dict)
            ],
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "run_id": self.run_id,
            "scenario_id": self.scenario_id,
            "mode": self.mode.value,
            "status": self.status.value,
            "started_at": self.started_at.isoformat(),
            "finished_at": self.finished_at.isoformat() if self.finished_at else None,
            "next_step_index": self.next_step_index,
            "completed_steps": self.completed_steps,
            "failed_step": self.failed_step,
            "notes": self.notes,
            "changed_files": self.changed_files,
            "step_results": [item.to_dict() for item in self.step_results],
        }


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
    if value in (None, ""):
        return None
    return str(value)


def _as_str_list(value: Any) -> list[str]:
    if not value:
        return []
    if isinstance(value, list):
        return [str(item) for item in value]
    return [str(value)]
