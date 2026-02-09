from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any


class ItemKind(str, Enum):
    IDEA = "idea"
    EXPERIMENT = "experiment"
    PREPROJECT = "preproject"
    PROJECT = "project"
    FEATURE = "feature"


@dataclass(slots=True)
class SourceRef:
    note_path: str
    note_title: str
    heading: str | None = None
    block_id: str | None = None
    excerpt: str | None = None
    captured_at: datetime = field(default_factory=lambda: utc_now())

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "SourceRef":
        return cls(
            note_path=str(data.get("note_path", "")),
            note_title=str(data.get("note_title", "")),
            heading=_as_optional_str(data.get("heading")),
            block_id=_as_optional_str(data.get("block_id")),
            excerpt=_as_optional_str(data.get("excerpt")),
            captured_at=parse_datetime(data.get("captured_at")),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "note_path": self.note_path,
            "note_title": self.note_title,
            "heading": self.heading,
            "block_id": self.block_id,
            "excerpt": self.excerpt,
            "captured_at": self.captured_at.isoformat(),
        }


@dataclass(slots=True)
class IngestedItem:
    item_id: str
    kind: ItemKind
    title: str
    description: str
    project_id: str | None = None
    feature_id: str | None = None
    confidence: float = 0.0
    tags: list[str] = field(default_factory=list)
    source_refs: list[SourceRef] = field(default_factory=list)
    approved: bool = False
    created_at: datetime = field(default_factory=lambda: utc_now())
    updated_at: datetime = field(default_factory=lambda: utc_now())

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "IngestedItem":
        return cls(
            item_id=str(data.get("item_id", "")),
            kind=ItemKind(str(data.get("kind", ItemKind.IDEA.value))),
            title=str(data.get("title", "")),
            description=str(data.get("description", "")),
            project_id=_as_optional_str(data.get("project_id")),
            feature_id=_as_optional_str(data.get("feature_id")),
            confidence=float(data.get("confidence", 0.0)),
            tags=_as_str_list(data.get("tags")),
            source_refs=[
                SourceRef.from_dict(item)
                for item in data.get("source_refs", [])
                if isinstance(item, dict)
            ],
            approved=bool(data.get("approved", False)),
            created_at=parse_datetime(data.get("created_at")),
            updated_at=parse_datetime(data.get("updated_at")),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "item_id": self.item_id,
            "kind": self.kind.value,
            "title": self.title,
            "description": self.description,
            "project_id": self.project_id,
            "feature_id": self.feature_id,
            "confidence": self.confidence,
            "tags": self.tags,
            "source_refs": [item.to_dict() for item in self.source_refs],
            "approved": self.approved,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
        }


@dataclass(slots=True)
class DuplicateCandidate:
    primary_id: str
    duplicate_id: str
    score: float
    reason: str


@dataclass(slots=True)
class IngestReviewItem:
    item_id: str
    confidence: float
    reason: str


@dataclass(slots=True)
class IngestState:
    last_scan_time: datetime | None = None
    file_hash_index: dict[str, str] = field(default_factory=dict)
    last_successful_run_id: str | None = None

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "IngestState":
        return cls(
            last_scan_time=parse_datetime_or_none(data.get("last_scan_time")),
            file_hash_index={
                str(k): str(v)
                for k, v in (data.get("file_hash_index", {}) or {}).items()
            },
            last_successful_run_id=_as_optional_str(data.get("last_successful_run_id")),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "last_scan_time": self.last_scan_time.isoformat() if self.last_scan_time else None,
            "file_hash_index": self.file_hash_index,
            "last_successful_run_id": self.last_successful_run_id,
        }


@dataclass(slots=True)
class ObsidianIngestResult:
    run_id: str
    notes_scanned: int
    items_created: int
    items_updated: int
    low_confidence_items: list[IngestReviewItem]
    duplicate_candidates: list[DuplicateCandidate]


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
