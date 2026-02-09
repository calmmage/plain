from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable

from plain.components.c1_flow.service import FlowService
from plain.components.c6_review.models import (
    FeedbackEntry,
    FeedbackVerdict,
    ReviewIngestResult,
    ReviewInstruction,
    ReviewItem,
    ReviewStatus,
    utc_now,
)
from plain.components.c6_review.repository import ReviewRepository
from plain.core.models import FlowError


@dataclass(slots=True)
class ParsedReviewPacket:
    source_ref: str
    summary: str
    task_key: str | None
    run_instructions: list[ReviewInstruction]
    changed_files: list[str]
    source_refs: list[str]
    conversation_refs: list[str]
    project_id: str | None = None
    feature_id: str | None = None
    original_vision: str | None = None


@dataclass(slots=True)
class ReviewService:
    repository: ReviewRepository
    flow_service: FlowService | None = None
    workspace: Path = Path(".")

    @classmethod
    def create_default(cls) -> "ReviewService":
        return cls(repository=ReviewRepository(), flow_service=FlowService.create_default())

    def ingest_packets(
        self,
        packet_sources: Iterable[str | Path] | None = None,
        project_id: str | None = None,
        feature_id: str | None = None,
        original_vision: str | None = None,
    ) -> ReviewIngestResult:
        sources = packet_sources or [Path("dev/notes/ecosystem/review_packets")]
        packets = self._collect_packets(sources)
        items = self.repository.load_items()

        by_id = {item.review_id: item for item in items}
        by_source: dict[str, str] = {}
        for item in items:
            for source in item.source_refs:
                by_source[source] = item.review_id

        created = 0
        updated = 0
        blocked = 0

        for packet in packets:
            resolved_project = packet.project_id or project_id or "unknown_project"
            resolved_feature = packet.feature_id or feature_id or packet.task_key or "unknown_feature"
            resolved_vision = (
                packet.original_vision
                or original_vision
                or self._lookup_vision(resolved_project, resolved_feature)
                or ""
            )

            status = ReviewStatus.READY
            if not resolved_vision.strip():
                status = ReviewStatus.CHANGES_REQUESTED
                blocked += 1

            existing_id = by_source.get(packet.source_ref)
            if existing_id and existing_id in by_id:
                item = by_id[existing_id]
                item.project_id = resolved_project
                item.feature_id = resolved_feature
                item.task_key = packet.task_key
                item.original_vision = resolved_vision
                item.summary = packet.summary
                item.status = status
                item.run_instructions = packet.run_instructions
                item.changed_files = packet.changed_files
                item.source_refs = sorted(set(packet.source_refs or [packet.source_ref]))
                item.conversation_refs = sorted(set(packet.conversation_refs))
                item.updated_at = utc_now()
                updated += 1
            else:
                review_id = self._next_review_id(packet.source_ref, set(by_id))
                item = ReviewItem(
                    review_id=review_id,
                    project_id=resolved_project,
                    feature_id=resolved_feature,
                    task_key=packet.task_key,
                    original_vision=resolved_vision,
                    summary=packet.summary,
                    status=status,
                    run_instructions=packet.run_instructions,
                    changed_files=packet.changed_files,
                    source_refs=sorted(set(packet.source_refs or [packet.source_ref])),
                    conversation_refs=sorted(set(packet.conversation_refs)),
                    created_at=utc_now(),
                    updated_at=utc_now(),
                )
                by_id[item.review_id] = item
                created += 1

            by_source[packet.source_ref] = item.review_id

        self.repository.save_items(
            sorted(
                by_id.values(),
                key=lambda item: (_status_rank(item.status), -item.updated_at.timestamp()),
            )
        )

        return ReviewIngestResult(
            packets_scanned=len(packets),
            items_created=created,
            items_updated=updated,
            blocked_items=blocked,
        )

    def list_items(
        self,
        status: str | None = None,
        ready_only: bool = False,
    ) -> list[ReviewItem]:
        items = self.repository.load_items()

        if status:
            target = ReviewStatus(status)
            items = [item for item in items if item.status == target]

        if ready_only:
            items = [item for item in items if item.status == ReviewStatus.READY]

        return sorted(
            items,
            key=lambda item: (_status_rank(item.status), -item.updated_at.timestamp()),
        )

    def get_item(self, review_id: str) -> ReviewItem:
        for item in self.repository.load_items():
            if item.review_id == review_id:
                return item
        raise FlowError(f"Review item not found: {review_id}")

    def get_feedback(self, review_id: str | None = None) -> list[FeedbackEntry]:
        entries = self.repository.load_feedback()
        if review_id:
            entries = [entry for entry in entries if entry.review_id == review_id]
        return sorted(entries, key=lambda item: item.created_at)

    def start_review(self, review_id: str) -> ReviewItem:
        item = self._set_status(review_id, ReviewStatus.IN_REVIEW)
        self.add_feedback(
            review_id=review_id,
            verdict=FeedbackVerdict.QUESTION.value,
            notes="Review started",
            author="system",
        )
        return item

    def approve(self, review_id: str, notes: str = "", author: str = "human") -> ReviewItem:
        item = self.get_item(review_id)
        if not item.original_vision.strip():
            raise FlowError("Cannot approve review item without original vision")
        item = self._set_status(review_id, ReviewStatus.APPROVED)
        self.add_feedback(
            review_id=review_id,
            verdict=FeedbackVerdict.APPROVE.value,
            notes=notes or "Approved",
            author=author,
        )
        return item

    def request_changes(
        self,
        review_id: str,
        notes: str,
        tags: Iterable[str] | None = None,
        author: str = "human",
    ) -> ReviewItem:
        if not notes.strip():
            raise FlowError("request_changes notes are required")
        item = self._set_status(review_id, ReviewStatus.CHANGES_REQUESTED)
        self.add_feedback(
            review_id=review_id,
            verdict=FeedbackVerdict.REQUEST_CHANGES.value,
            notes=notes,
            tags=tags,
            author=author,
        )
        return item

    def reject(
        self,
        review_id: str,
        notes: str,
        tags: Iterable[str] | None = None,
        author: str = "human",
    ) -> ReviewItem:
        if not notes.strip():
            raise FlowError("reject notes are required")
        item = self._set_status(review_id, ReviewStatus.REJECTED)
        self.add_feedback(
            review_id=review_id,
            verdict=FeedbackVerdict.REJECT.value,
            notes=notes,
            tags=tags,
            author=author,
        )
        return item

    def add_feedback(
        self,
        review_id: str,
        verdict: str,
        notes: str,
        tags: Iterable[str] | None = None,
        author: str = "human",
    ) -> FeedbackEntry:
        self.get_item(review_id)
        entry = FeedbackEntry(
            review_id=review_id,
            author=author,
            verdict=FeedbackVerdict(verdict),
            notes=notes.strip(),
            tags=[str(tag).strip() for tag in (tags or []) if str(tag).strip()],
            created_at=utc_now(),
        )

        entries = self.repository.load_feedback()
        entries.append(entry)
        self.repository.save_feedback(entries)
        return entry

    def get_run_instruction(self, review_id: str, index: int = 0) -> ReviewInstruction:
        item = self.get_item(review_id)
        if not item.run_instructions:
            raise FlowError(f"No run instructions for {review_id}")
        if index < 0 or index >= len(item.run_instructions):
            raise FlowError(f"Instruction index out of range: {index}")
        return item.run_instructions[index]

    def _set_status(self, review_id: str, target_status: ReviewStatus) -> ReviewItem:
        items = self.repository.load_items()
        for item in items:
            if item.review_id != review_id:
                continue
            if target_status == ReviewStatus.READY and not item.original_vision.strip():
                raise FlowError("Cannot set READY without original vision")
            if item.status == ReviewStatus.REJECTED and target_status != ReviewStatus.REJECTED:
                raise FlowError("Rejected item cannot transition to another status")
            item.status = target_status
            item.updated_at = utc_now()
            self.repository.save_items(items)
            return item

        raise FlowError(f"Review item not found: {review_id}")

    def _collect_packets(self, sources: Iterable[str | Path]) -> list[ParsedReviewPacket]:
        packets: list[ParsedReviewPacket] = []
        for source in sources:
            path = self._resolve(source)
            if not path.exists():
                continue
            if path.is_dir():
                for item in sorted(path.rglob("*")):
                    if not item.is_file() or item.suffix.lower() not in {".md", ".json"}:
                        continue
                    packets.extend(self._parse_packet(item))
                continue
            packets.extend(self._parse_packet(path))
        return packets

    def _parse_packet(self, path: Path) -> list[ParsedReviewPacket]:
        if path.suffix.lower() == ".json":
            return self._parse_json_packet(path)
        if path.suffix.lower() == ".md":
            return [self._parse_markdown_packet(path)]
        return []

    def _parse_json_packet(self, path: Path) -> list[ParsedReviewPacket]:
        try:
            payload = json.loads(path.read_text())
        except Exception:
            return []

        rows: list[dict[str, Any]] = []
        if isinstance(payload, list):
            rows = [row for row in payload if isinstance(row, dict)]
        elif isinstance(payload, dict):
            nested = payload.get("items")
            if isinstance(nested, list):
                rows = [row for row in nested if isinstance(row, dict)]
            else:
                rows = [payload]

        packets: list[ParsedReviewPacket] = []
        for idx, row in enumerate(rows, start=1):
            source_ref = str(path) if len(rows) == 1 else f"{path}#{idx}"
            cwd = str(row.get("cwd") or row.get("workspace_path") or ".")
            instructions = _coerce_instructions(row.get("run_instructions"), cwd)
            if not instructions:
                instructions = [ReviewInstruction(title="open_review", command="git status --short", cwd=cwd)]

            summary = str(row.get("summary") or row.get("title") or f"Review item from {path.name}")
            changed_files = [str(item) for item in row.get("changed_files", []) if str(item).strip()]

            packets.append(
                ParsedReviewPacket(
                    source_ref=source_ref,
                    summary=summary.strip(),
                    task_key=_as_optional_str(row.get("task_key")),
                    run_instructions=instructions,
                    changed_files=changed_files,
                    source_refs=[source_ref],
                    conversation_refs=_as_str_list(row.get("conversation_refs")),
                    project_id=_as_optional_str(row.get("project_id")),
                    feature_id=_as_optional_str(row.get("feature_id")),
                    original_vision=_as_optional_str(row.get("original_vision")),
                )
            )
        return packets

    def _parse_markdown_packet(self, path: Path) -> ParsedReviewPacket:
        text = path.read_text(errors="ignore")
        lines = text.splitlines()

        metadata: dict[str, str] = {}
        for line in lines:
            if line.startswith("## "):
                break
            match = re.match(r"^\s*-\s*(?P<key>[a-zA-Z0-9_\- ]+):\s*(?P<value>.+?)\s*$", line)
            if not match:
                continue
            key = match.group("key").strip().lower().replace(" ", "_")
            metadata[key] = match.group("value").strip()

        sections = _split_sections(lines)
        summary = "\n".join(sections.get("summary", [])).strip()
        if not summary:
            summary = metadata.get("task") or f"Review packet from {path.name}"

        cwd = metadata.get("workspace_path", ".")
        run_lines = _section_bullets(sections.get("run/test_instructions", []))
        instructions = _coerce_instructions(run_lines, cwd)
        if not instructions:
            instructions = [ReviewInstruction(title="open_review", command="git status --short", cwd=cwd)]

        changed_files = [
            item
            for item in _section_bullets(sections.get("changed_files", []))
            if item.lower() != "none (implementation loop placeholder)"
        ]

        task_key = _task_key_from_name(path) or _as_optional_str(metadata.get("task"))
        conversation_refs = _section_bullets(sections.get("conversations", []))

        return ParsedReviewPacket(
            source_ref=str(path),
            summary=summary,
            task_key=task_key,
            run_instructions=instructions,
            changed_files=changed_files,
            source_refs=[str(path)],
            conversation_refs=conversation_refs,
            project_id=_as_optional_str(metadata.get("project_id")),
            feature_id=_as_optional_str(metadata.get("feature_id")),
            original_vision=_as_optional_str(metadata.get("original_vision")),
        )

    def _lookup_vision(self, project_id: str, feature_id: str) -> str | None:
        if not self.flow_service:
            return None
        if project_id.startswith("unknown_") or feature_id.startswith("unknown_"):
            return None
        try:
            feature = self.flow_service.get_feature(project_id, feature_id)
        except FlowError:
            return None
        return feature.vision.strip() if feature.vision else None

    def _next_review_id(self, source_ref: str, existing: set[str]) -> str:
        digest = hashlib.sha1(source_ref.encode("utf-8")).hexdigest()[:10]
        candidate = f"rev_{digest}"
        idx = 2
        while candidate in existing:
            candidate = f"rev_{digest}_{idx}"
            idx += 1
        return candidate

    def _resolve(self, path: str | Path) -> Path:
        candidate = Path(path)
        if candidate.is_absolute():
            return candidate
        return self.workspace / candidate


def _coerce_instructions(raw: Any, cwd: str) -> list[ReviewInstruction]:
    if not raw:
        return []

    if isinstance(raw, str):
        raw = [raw]

    instructions: list[ReviewInstruction] = []
    if isinstance(raw, list):
        for idx, row in enumerate(raw, start=1):
            if isinstance(row, dict):
                item = ReviewInstruction.from_dict(row)
                if not item.cwd:
                    item.cwd = cwd
                instructions.append(item)
                continue
            text = str(row).strip()
            if not text:
                continue
            command, expected = _instruction_command(text)
            instructions.append(
                ReviewInstruction(
                    title=f"step_{idx}",
                    command=command,
                    cwd=cwd,
                    expected_result=expected,
                )
            )
    return instructions


def _instruction_command(text: str) -> tuple[str, str | None]:
    lowered = text.lower()
    if lowered.startswith(("uv ", "python ", "make ", "pytest ", "git ", "npm ", "pnpm ")):
        return text, None
    if "run project tests" in lowered:
        return "uv run pytest src tests", text
    if "reproduce changes locally" in lowered:
        return "git status --short", text
    if "address unresolved issues" in lowered:
        return "echo \"Address unresolved issues before continuing\"", text
    return f"echo \"{_shell_safe(text)}\"", text


def _split_sections(lines: list[str]) -> dict[str, list[str]]:
    sections: dict[str, list[str]] = {}
    current = "_top"
    sections[current] = []
    for line in lines:
        if line.startswith("## "):
            current = line.lstrip("#").strip().lower().replace(" ", "_")
            sections.setdefault(current, [])
            continue
        sections.setdefault(current, []).append(line)
    return sections


def _section_bullets(lines: list[str]) -> list[str]:
    out: list[str] = []
    for line in lines:
        match = re.match(r"^\s*-\s*(.+?)\s*$", line)
        if not match:
            continue
        item = match.group(1).strip()
        if item:
            out.append(item)
    return out


def _task_key_from_name(path: Path) -> str | None:
    match = re.match(r"^\d{4}-\d{2}-\d{2}-(?P<key>[^.]+)", path.name)
    if not match:
        return None
    return match.group("key")


def _as_optional_str(value: Any) -> str | None:
    if value in (None, ""):
        return None
    return str(value)


def _as_str_list(value: Any) -> list[str]:
    if not value:
        return []
    if isinstance(value, list):
        return [str(item) for item in value if str(item).strip()]
    return [str(value)]


def _status_rank(status: ReviewStatus) -> int:
    if status == ReviewStatus.READY:
        return 0
    if status == ReviewStatus.IN_REVIEW:
        return 1
    if status == ReviewStatus.CHANGES_REQUESTED:
        return 2
    if status == ReviewStatus.APPROVED:
        return 3
    return 4


def _shell_safe(text: str) -> str:
    return text.replace("\\", "\\\\").replace('"', '\\"')
