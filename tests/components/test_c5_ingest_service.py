from __future__ import annotations

import shutil
from pathlib import Path

from plain.components.c5_ingest.models import DuplicateCandidate, IngestReviewItem, ItemKind
from plain.components.c5_ingest.repository import ObsidianIngestRepository
from plain.components.c5_ingest.service import ObsidianIngestService


def _service(tmp_path: Path) -> ObsidianIngestService:
    repo = ObsidianIngestRepository(
        base_dir=tmp_path / "data/obsidian_ingest",
        state_path=tmp_path / "dev/notes/ecosystem/state/obsidian_ingest_state.json",
    )
    return ObsidianIngestService(repository=repo, workspace=tmp_path)


def _copy_fixture_vault(tmp_path: Path) -> None:
    shutil.copytree(Path("tests/fixtures/c5/obsidian"), tmp_path / "obsidian")


def test_run_ingest_extracts_items_with_backlinks(tmp_path: Path) -> None:
    _copy_fixture_vault(tmp_path)
    service = _service(tmp_path)

    result = service.run_ingest(force_full_scan=True)

    assert result.notes_scanned == 4
    assert result.items_created >= 8

    items = service.get_items()
    assert items
    assert all(item.source_refs for item in items)
    assert any(item.kind == ItemKind.FEATURE for item in items)
    assert any(item.kind == ItemKind.EXPERIMENT for item in items)
    assert any(
        item.kind == ItemKind.PREPROJECT and "preproject" in item.title.lower()
        for item in items
    )

    state = service.repository.load_state()
    assert state.last_successful_run_id == result.run_id
    assert len(state.file_hash_index) == 4


def test_incremental_scan_skips_unchanged_and_processes_modified_note(tmp_path: Path) -> None:
    _copy_fixture_vault(tmp_path)
    service = _service(tmp_path)

    service.run_ingest(force_full_scan=True)
    second = service.run_ingest()
    assert second.notes_scanned == 0
    assert second.items_created == 0
    assert second.items_updated == 0

    daily_note = tmp_path / "obsidian/daily/2026-02-09.md"
    daily_note.write_text(
        daily_note.read_text() + "\n- Feature: Backlink graph explorer for review queue\n"
    )

    third = service.run_ingest()
    assert third.notes_scanned == 1
    assert third.items_created >= 1
    assert third.items_updated >= 1

    features = service.get_items(kind=ItemKind.FEATURE.value)
    assert any("Backlink graph explorer" in item.title for item in features)


def test_get_items_filters_by_kind_and_confidence(tmp_path: Path) -> None:
    _copy_fixture_vault(tmp_path)
    service = _service(tmp_path)
    service.run_ingest(force_full_scan=True)

    features = service.get_items(kind=ItemKind.FEATURE.value)
    assert features
    assert all(item.kind == ItemKind.FEATURE for item in features)

    high_confidence = service.get_items(min_confidence=0.8)
    assert high_confidence
    assert all(item.confidence >= 0.8 for item in high_confidence)


def test_pending_review_and_approve_flow(tmp_path: Path) -> None:
    _copy_fixture_vault(tmp_path)
    service = _service(tmp_path)
    service.run_ingest(force_full_scan=True)

    pending = service.get_pending_review_items()
    assert pending

    approved = service.approve_item(pending[0].item_id)
    assert approved.approved is True

    remaining_ids = {item.item_id for item in service.get_pending_review_items()}
    assert approved.item_id not in remaining_ids


def test_merge_and_reclassify_flow(tmp_path: Path) -> None:
    _copy_fixture_vault(tmp_path)
    service = _service(tmp_path)
    service.run_ingest(force_full_scan=True)

    items = service.get_items()
    primary = items[0]
    duplicate = items[1]

    primary.tags = ["alpha"]
    duplicate.tags = ["beta"]
    primary_ref_count = len(primary.source_refs)
    duplicate_ref_count = len(duplicate.source_refs)

    service.repository.save_items(items)
    service.repository.save_review_queue(
        [
            IngestReviewItem(item_id=primary.item_id, confidence=0.4, reason="manual_check"),
            IngestReviewItem(item_id=duplicate.item_id, confidence=0.3, reason="manual_check"),
        ]
    )
    service.repository.save_duplicates(
        [
            DuplicateCandidate(
                primary_id=primary.item_id,
                duplicate_id=duplicate.item_id,
                score=0.91,
                reason="title_similarity",
            )
        ]
    )

    merged = service.merge_items(primary.item_id, duplicate.item_id)
    assert merged.item_id == primary.item_id

    merged_item = service.get_item_with_sources(primary.item_id)
    assert "beta" in merged_item.tags
    assert len(merged_item.source_refs) >= primary_ref_count + duplicate_ref_count
    assert duplicate.item_id not in {item.item_id for item in service.get_items()}
    assert all(
        row.item_id not in {primary.item_id, duplicate.item_id}
        for row in service.repository.load_review_queue()
    )
    assert all(
        row.duplicate_id != duplicate.item_id and row.primary_id != duplicate.item_id
        for row in service.repository.load_duplicates()
    )

    reclassified = service.reclassify_item(primary.item_id, ItemKind.PROJECT.value)
    assert reclassified.kind == ItemKind.PROJECT
