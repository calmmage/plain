from __future__ import annotations

import json
from pathlib import Path

from plain.components.c6_review.models import FeedbackEntry, ReviewItem


class ReviewRepository:
    def __init__(self, base_dir: Path | str = Path("data/review_queue")):
        self.base_dir = Path(base_dir)

    @property
    def items_path(self) -> Path:
        return self.base_dir / "items.json"

    @property
    def feedback_path(self) -> Path:
        return self.base_dir / "feedback.json"

    def ensure_dirs(self) -> None:
        self.base_dir.mkdir(parents=True, exist_ok=True)

    def load_items(self) -> list[ReviewItem]:
        self.ensure_dirs()
        if not self.items_path.exists():
            return []

        try:
            payload = json.loads(self.items_path.read_text())
        except Exception:
            return []

        if not isinstance(payload, list):
            return []

        items: list[ReviewItem] = []
        for row in payload:
            if isinstance(row, dict):
                items.append(ReviewItem.from_dict(row))
        return items

    def save_items(self, items: list[ReviewItem]) -> None:
        self.ensure_dirs()
        payload = [item.to_dict() for item in items]
        self.items_path.write_text(json.dumps(payload, indent=2) + "\n")

    def load_feedback(self) -> list[FeedbackEntry]:
        self.ensure_dirs()
        if not self.feedback_path.exists():
            return []

        try:
            payload = json.loads(self.feedback_path.read_text())
        except Exception:
            return []

        if not isinstance(payload, list):
            return []

        entries: list[FeedbackEntry] = []
        for row in payload:
            if isinstance(row, dict):
                entries.append(FeedbackEntry.from_dict(row))
        return entries

    def save_feedback(self, entries: list[FeedbackEntry]) -> None:
        self.ensure_dirs()
        payload = [entry.to_dict() for entry in entries]
        self.feedback_path.write_text(json.dumps(payload, indent=2) + "\n")
