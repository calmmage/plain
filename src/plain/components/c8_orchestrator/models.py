from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any


@dataclass(slots=True)
class ModuleStatus:
    module_id: str
    title: str
    status: str
    details: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class WorkflowStatusSnapshot:
    generated_at: datetime
    modules: list[ModuleStatus]


def utc_now() -> datetime:
    return datetime.now(timezone.utc).replace(microsecond=0)
