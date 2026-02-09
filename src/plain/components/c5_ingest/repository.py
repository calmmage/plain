from __future__ import annotations

import json
from pathlib import Path

from plain.components.c5_ingest.models import (
    DuplicateCandidate,
    IngestReviewItem,
    IngestState,
    IngestedItem,
    ObsidianIngestResult,
)


class ObsidianIngestRepository:
    def __init__(
        self,
        base_dir: Path | str = Path("data/obsidian_ingest"),
        state_path: Path | str = Path(
            "dev/notes/ecosystem/state/obsidian_ingest_state.json"
        ),
    ):
        self.base_dir = Path(base_dir)
        self.state_path = Path(state_path)

    @property
    def items_path(self) -> Path:
        return self.base_dir / "items.json"

    @property
    def review_queue_path(self) -> Path:
        return self.base_dir / "review_queue.json"

    @property
    def duplicates_path(self) -> Path:
        return self.base_dir / "duplicates.json"

    @property
    def runs_path(self) -> Path:
        return self.base_dir / "runs"

    def ensure_dirs(self) -> None:
        self.base_dir.mkdir(parents=True, exist_ok=True)
        self.runs_path.mkdir(parents=True, exist_ok=True)
        self.state_path.parent.mkdir(parents=True, exist_ok=True)

    def load_items(self) -> list[IngestedItem]:
        self.ensure_dirs()
        if not self.items_path.exists():
            return []

        try:
            payload = json.loads(self.items_path.read_text())
        except Exception:
            return []

        if not isinstance(payload, list):
            return []

        items: list[IngestedItem] = []
        for row in payload:
            if isinstance(row, dict):
                items.append(IngestedItem.from_dict(row))
        return items

    def save_items(self, items: list[IngestedItem]) -> None:
        self.ensure_dirs()
        payload = [item.to_dict() for item in items]
        self.items_path.write_text(json.dumps(payload, indent=2) + "\n")

    def load_state(self) -> IngestState:
        self.ensure_dirs()
        if not self.state_path.exists():
            return IngestState()

        try:
            payload = json.loads(self.state_path.read_text())
        except Exception:
            return IngestState()

        if not isinstance(payload, dict):
            return IngestState()

        return IngestState.from_dict(payload)

    def save_state(self, state: IngestState) -> None:
        self.ensure_dirs()
        self.state_path.write_text(json.dumps(state.to_dict(), indent=2) + "\n")

    def load_review_queue(self) -> list[IngestReviewItem]:
        self.ensure_dirs()
        if not self.review_queue_path.exists():
            return []

        try:
            payload = json.loads(self.review_queue_path.read_text())
        except Exception:
            return []

        if not isinstance(payload, list):
            return []

        queue: list[IngestReviewItem] = []
        for row in payload:
            if not isinstance(row, dict):
                continue
            queue.append(
                IngestReviewItem(
                    item_id=str(row.get("item_id", "")),
                    confidence=float(row.get("confidence", 0.0)),
                    reason=str(row.get("reason", "")),
                )
            )
        return queue

    def save_review_queue(self, queue: list[IngestReviewItem]) -> None:
        self.ensure_dirs()
        payload = [
            {
                "item_id": row.item_id,
                "confidence": row.confidence,
                "reason": row.reason,
            }
            for row in queue
        ]
        self.review_queue_path.write_text(json.dumps(payload, indent=2) + "\n")

    def load_duplicates(self) -> list[DuplicateCandidate]:
        self.ensure_dirs()
        if not self.duplicates_path.exists():
            return []

        try:
            payload = json.loads(self.duplicates_path.read_text())
        except Exception:
            return []

        if not isinstance(payload, list):
            return []

        out: list[DuplicateCandidate] = []
        for row in payload:
            if not isinstance(row, dict):
                continue
            out.append(
                DuplicateCandidate(
                    primary_id=str(row.get("primary_id", "")),
                    duplicate_id=str(row.get("duplicate_id", "")),
                    score=float(row.get("score", 0.0)),
                    reason=str(row.get("reason", "")),
                )
            )
        return out

    def save_duplicates(self, duplicates: list[DuplicateCandidate]) -> None:
        self.ensure_dirs()
        payload = [
            {
                "primary_id": item.primary_id,
                "duplicate_id": item.duplicate_id,
                "score": item.score,
                "reason": item.reason,
            }
            for item in duplicates
        ]
        self.duplicates_path.write_text(json.dumps(payload, indent=2) + "\n")

    def save_run_result(self, result: ObsidianIngestResult) -> Path:
        self.ensure_dirs()
        path = self.runs_path / f"{result.run_id}.json"
        payload = {
            "run_id": result.run_id,
            "notes_scanned": result.notes_scanned,
            "items_created": result.items_created,
            "items_updated": result.items_updated,
            "low_confidence_items": [
                {
                    "item_id": item.item_id,
                    "confidence": item.confidence,
                    "reason": item.reason,
                }
                for item in result.low_confidence_items
            ],
            "duplicate_candidates": [
                {
                    "primary_id": item.primary_id,
                    "duplicate_id": item.duplicate_id,
                    "score": item.score,
                    "reason": item.reason,
                }
                for item in result.duplicate_candidates
            ],
        }
        path.write_text(json.dumps(payload, indent=2) + "\n")
        return path
