from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass
from difflib import SequenceMatcher
from pathlib import Path
from typing import Iterable

from plain.components.c5_ingest.models import (
    DuplicateCandidate,
    IngestReviewItem,
    IngestState,
    IngestedItem,
    ItemKind,
    ObsidianIngestResult,
    SourceRef,
    utc_now,
)
from plain.components.c5_ingest.repository import ObsidianIngestRepository
from plain.core.models import FlowError

FOLDER_KIND_DEFAULTS = {
    "daily": ItemKind.IDEA,
    "dumps": ItemKind.IDEA,
    "workalongs": ItemKind.EXPERIMENT,
    "preproject": ItemKind.PREPROJECT,
}


@dataclass(slots=True)
class ExtractedCandidate:
    kind: ItemKind
    title: str
    description: str
    confidence: float
    tags: list[str]
    heading: str | None
    excerpt: str | None


@dataclass(slots=True)
class ObsidianIngestService:
    repository: ObsidianIngestRepository
    workspace: Path = Path(".")

    @classmethod
    def create_default(cls) -> "ObsidianIngestService":
        return cls(repository=ObsidianIngestRepository())

    def run_ingest(
        self,
        note_roots: Iterable[str | Path] | None = None,
        force_full_scan: bool = False,
    ) -> ObsidianIngestResult:
        roots = [self._resolve(path) for path in (note_roots or _default_note_roots())]
        state = self.repository.load_state()
        existing_items = self.repository.load_items()
        by_id = {item.item_id: item for item in existing_items}

        changed_notes, hash_index = self._discover_changed_notes(roots, state, force_full_scan)

        created = 0
        updated = 0
        low_confidence: list[IngestReviewItem] = []
        duplicates: list[DuplicateCandidate] = self.repository.load_duplicates()

        for note_path in changed_notes:
            extracted = self._extract_candidates(note_path)
            for candidate in extracted:
                source_ref = self._build_source_ref(note_path, candidate)
                matched = self._find_existing_match(candidate, list(by_id.values()))

                if matched and matched[1] >= 0.96:
                    item = matched[0]
                    item.description = candidate.description
                    item.kind = candidate.kind
                    item.confidence = max(item.confidence, candidate.confidence)
                    item.tags = sorted(set(item.tags + candidate.tags))
                    item.source_refs.append(source_ref)
                    item.updated_at = utc_now()
                    by_id[item.item_id] = item
                    updated += 1
                else:
                    item_id = self._next_item_id(note_path, candidate.title)
                    item = IngestedItem(
                        item_id=item_id,
                        kind=candidate.kind,
                        title=candidate.title,
                        description=candidate.description,
                        confidence=candidate.confidence,
                        tags=candidate.tags,
                        source_refs=[source_ref],
                        created_at=utc_now(),
                        updated_at=utc_now(),
                    )
                    by_id[item.item_id] = item
                    created += 1

                    if matched and matched[1] >= 0.86:
                        duplicates.append(
                            DuplicateCandidate(
                                primary_id=matched[0].item_id,
                                duplicate_id=item.item_id,
                                score=round(matched[1], 3),
                                reason="title_similarity",
                            )
                        )

                if candidate.confidence < 0.6:
                    low_confidence.append(
                        IngestReviewItem(
                            item_id=item.item_id,
                            confidence=candidate.confidence,
                            reason="low_confidence_extraction",
                        )
                    )

        run_id = utc_now().strftime("ingest_%Y%m%d_%H%M%S")

        items = sorted(by_id.values(), key=lambda item: item.updated_at)
        self.repository.save_items(items)
        self.repository.save_review_queue(_dedupe_review_items(low_confidence))
        self.repository.save_duplicates(_dedupe_duplicates(duplicates))

        next_state = IngestState(
            last_scan_time=utc_now(),
            file_hash_index=hash_index,
            last_successful_run_id=run_id,
        )
        self.repository.save_state(next_state)

        result = ObsidianIngestResult(
            run_id=run_id,
            notes_scanned=len(changed_notes),
            items_created=created,
            items_updated=updated,
            low_confidence_items=_dedupe_review_items(low_confidence),
            duplicate_candidates=_dedupe_duplicates(duplicates),
        )
        self.repository.save_run_result(result)
        return result

    # Downstream APIs
    def get_items(
        self,
        kind: str | None = None,
        project_id: str | None = None,
        min_confidence: float = 0.0,
    ) -> list[IngestedItem]:
        items = self.repository.load_items()

        if kind:
            target = ItemKind(kind)
            items = [item for item in items if item.kind == target]

        if project_id:
            items = [item for item in items if item.project_id == project_id]

        if min_confidence > 0:
            items = [item for item in items if item.confidence >= min_confidence]

        return sorted(items, key=lambda item: (-item.confidence, item.title.lower()))

    def get_item_with_sources(self, item_id: str) -> IngestedItem:
        for item in self.repository.load_items():
            if item.item_id == item_id:
                return item
        raise FlowError(f"Ingested item not found: {item_id}")

    def get_pending_review_items(self) -> list[IngestedItem]:
        queue = self.repository.load_review_queue()
        queue_ids = {row.item_id for row in queue}
        return [item for item in self.repository.load_items() if item.item_id in queue_ids]

    def approve_item(self, item_id: str) -> IngestedItem:
        items = self.repository.load_items()
        found: IngestedItem | None = None
        for item in items:
            if item.item_id == item_id:
                item.approved = True
                item.updated_at = utc_now()
                found = item
                break

        if not found:
            raise FlowError(f"Ingested item not found: {item_id}")

        queue = [row for row in self.repository.load_review_queue() if row.item_id != item_id]
        self.repository.save_items(items)
        self.repository.save_review_queue(queue)
        return found

    def merge_items(self, primary_id: str, duplicate_id: str) -> IngestedItem:
        items = self.repository.load_items()
        primary = next((item for item in items if item.item_id == primary_id), None)
        duplicate = next((item for item in items if item.item_id == duplicate_id), None)

        if not primary or not duplicate:
            raise FlowError("Both primary and duplicate items are required for merge")

        primary.tags = sorted(set(primary.tags + duplicate.tags))
        primary.source_refs.extend(duplicate.source_refs)
        primary.confidence = max(primary.confidence, duplicate.confidence)
        primary.description = _longer_text(primary.description, duplicate.description)
        primary.updated_at = utc_now()

        items = [item for item in items if item.item_id != duplicate_id]
        self.repository.save_items(items)

        queue = [
            row
            for row in self.repository.load_review_queue()
            if row.item_id not in {primary_id, duplicate_id}
        ]
        self.repository.save_review_queue(queue)

        duplicates = [
            row
            for row in self.repository.load_duplicates()
            if row.duplicate_id != duplicate_id and row.primary_id != duplicate_id
        ]
        self.repository.save_duplicates(duplicates)

        return primary

    def reclassify_item(self, item_id: str, kind: str) -> IngestedItem:
        target_kind = ItemKind(kind)
        items = self.repository.load_items()
        for item in items:
            if item.item_id == item_id:
                item.kind = target_kind
                item.updated_at = utc_now()
                self.repository.save_items(items)
                return item

        raise FlowError(f"Ingested item not found: {item_id}")

    def _discover_changed_notes(
        self,
        roots: list[Path],
        state: IngestState,
        force_full_scan: bool,
    ) -> tuple[list[Path], dict[str, str]]:
        paths: list[Path] = []
        hash_index: dict[str, str] = {}

        for root in roots:
            if not root.exists():
                continue
            for path in sorted(root.rglob("*.md")):
                if not path.is_file():
                    continue
                digest = _sha1(path)
                hash_index[str(path)] = digest
                previous = state.file_hash_index.get(str(path))
                if force_full_scan or previous != digest:
                    paths.append(path)

        return paths, hash_index

    def _extract_candidates(self, note_path: Path) -> list[ExtractedCandidate]:
        text = note_path.read_text(errors="ignore")
        lines = text.splitlines()
        note_title = _extract_note_title(note_path, lines)
        default_kind = _default_kind_for_path(note_path)
        tags = _extract_tags(text)

        candidates: list[ExtractedCandidate] = []

        # Candidate from note title + first paragraph
        first_paragraph = _first_paragraph(lines)
        title_kind, title_conf = _classify_kind(note_title, default_kind)
        candidates.append(
            ExtractedCandidate(
                kind=title_kind,
                title=note_title,
                description=first_paragraph or note_title,
                confidence=title_conf,
                tags=tags,
                heading=None,
                excerpt=first_paragraph[:180] if first_paragraph else None,
            )
        )

        heading = None
        checklist_re = re.compile(r"^\s*[-*]\s*(?:\[[ xX]\]\s*)?(?P<text>.+)$")
        for line in lines:
            if line.startswith("#"):
                heading = line.lstrip("#").strip() or heading
                continue

            match = checklist_re.match(line)
            if not match:
                continue

            bullet = match.group("text").strip()
            if len(bullet) < 8:
                continue

            kind, conf = _classify_kind(bullet, default_kind)
            candidates.append(
                ExtractedCandidate(
                    kind=kind,
                    title=_title_from_text(bullet),
                    description=bullet,
                    confidence=conf,
                    tags=tags,
                    heading=heading,
                    excerpt=bullet[:180],
                )
            )

        # Deduplicate candidates by title+kind.
        deduped: dict[tuple[str, ItemKind], ExtractedCandidate] = {}
        for candidate in candidates:
            key = (_norm(candidate.title), candidate.kind)
            existing = deduped.get(key)
            if not existing or candidate.confidence > existing.confidence:
                deduped[key] = candidate

        return list(deduped.values())

    def _build_source_ref(self, note_path: Path, candidate: ExtractedCandidate) -> SourceRef:
        return SourceRef(
            note_path=str(note_path),
            note_title=note_path.stem,
            heading=candidate.heading,
            excerpt=candidate.excerpt,
            captured_at=utc_now(),
        )

    def _find_existing_match(
        self,
        candidate: ExtractedCandidate,
        items: list[IngestedItem],
    ) -> tuple[IngestedItem, float] | None:
        best_item: IngestedItem | None = None
        best_score = 0.0
        candidate_norm = _norm(candidate.title)

        for item in items:
            title_score = SequenceMatcher(None, candidate_norm, _norm(item.title)).ratio()
            kind_bonus = 0.04 if item.kind == candidate.kind else 0.0
            score = min(1.0, title_score + kind_bonus)
            if score > best_score:
                best_score = score
                best_item = item

        if best_item is None:
            return None
        return best_item, best_score

    def _next_item_id(self, note_path: Path, title: str) -> str:
        digest = hashlib.sha1(f"{note_path}:{title}".encode("utf-8")).hexdigest()[:10]
        stamp = utc_now().strftime("%Y%m%d")
        return f"itm_{stamp}_{digest}"

    def _resolve(self, path: str | Path) -> Path:
        candidate = Path(path)
        if candidate.is_absolute():
            return candidate
        return self.workspace / candidate


def _default_note_roots() -> list[str]:
    return [
        "obsidian/daily",
        "obsidian/preproject",
        "obsidian/workalongs",
        "obsidian/dumps",
    ]


def _sha1(path: Path) -> str:
    digest = hashlib.sha1()
    digest.update(path.read_bytes())
    return digest.hexdigest()


def _norm(text: str) -> str:
    return " ".join(text.lower().split())


def _extract_note_title(note_path: Path, lines: list[str]) -> str:
    for line in lines:
        if line.startswith("#"):
            title = line.lstrip("#").strip()
            if title:
                return title
    return note_path.stem.replace("_", " ").replace("-", " ").strip() or note_path.stem


def _first_paragraph(lines: list[str]) -> str:
    chunks: list[str] = []
    for line in lines:
        stripped = line.strip()
        if not stripped:
            if chunks:
                break
            continue
        if stripped.startswith("#"):
            continue
        chunks.append(stripped)
    return " ".join(chunks)


def _extract_tags(text: str) -> list[str]:
    tags = re.findall(r"#([a-zA-Z0-9_\-/]+)", text)
    return sorted(set(tags))[:20]


def _default_kind_for_path(note_path: Path) -> ItemKind:
    lowered = str(note_path).lower()
    for key, kind in FOLDER_KIND_DEFAULTS.items():
        if f"/{key}/" in lowered:
            return kind
    return ItemKind.IDEA


def _classify_kind(text: str, default_kind: ItemKind) -> tuple[ItemKind, float]:
    lowered = text.lower()

    if "feature" in lowered:
        return ItemKind.FEATURE, 0.86
    if "preproject" in lowered:
        return ItemKind.PREPROJECT, 0.88
    if re.search(r"\bproject\b", lowered):
        return ItemKind.PROJECT, 0.84
    if "experiment" in lowered or "try " in lowered:
        return ItemKind.EXPERIMENT, 0.8
    if "idea" in lowered:
        return ItemKind.IDEA, 0.76

    return default_kind, 0.58


def _title_from_text(text: str) -> str:
    cleaned = text.strip().rstrip(".")
    if len(cleaned) <= 70:
        return cleaned
    return cleaned[:67].rstrip() + "..."


def _dedupe_review_items(items: list[IngestReviewItem]) -> list[IngestReviewItem]:
    best: dict[str, IngestReviewItem] = {}
    for item in items:
        existing = best.get(item.item_id)
        if not existing or item.confidence < existing.confidence:
            best[item.item_id] = item
    return list(best.values())


def _dedupe_duplicates(items: list[DuplicateCandidate]) -> list[DuplicateCandidate]:
    best: dict[tuple[str, str], DuplicateCandidate] = {}
    for item in items:
        key = (item.primary_id, item.duplicate_id)
        existing = best.get(key)
        if not existing or item.score > existing.score:
            best[key] = item
    return list(best.values())


def _longer_text(primary: str, duplicate: str) -> str:
    return primary if len(primary) >= len(duplicate) else duplicate
