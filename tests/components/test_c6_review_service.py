from __future__ import annotations

import shutil
from pathlib import Path

import pytest

from plain.components.c6_review.models import ReviewStatus
from plain.components.c6_review.render import render_review_table
from plain.components.c6_review.repository import ReviewRepository
from plain.components.c6_review.service import ReviewService
from plain.core.models import FlowError


def _service(tmp_path: Path) -> ReviewService:
    return ReviewService(
        repository=ReviewRepository(base_dir=tmp_path / "data/review_queue"),
        flow_service=None,
        workspace=tmp_path,
    )


def _copy_review_packets(tmp_path: Path) -> Path:
    target = tmp_path / "review_packets"
    shutil.copytree(Path("tests/fixtures/c6/review_packets"), target)
    return target


def test_ingest_blocks_ready_status_without_original_vision(tmp_path: Path) -> None:
    packet_dir = _copy_review_packets(tmp_path)
    service = _service(tmp_path)

    result = service.ingest_packets(packet_sources=[packet_dir / "2026-02-09-al.md"])

    assert result.packets_scanned == 1
    assert result.items_created == 1
    assert result.blocked_items == 1

    items = service.list_items()
    assert len(items) == 1
    assert items[0].status == ReviewStatus.CHANGES_REQUESTED
    assert items[0].run_instructions
    assert len(items[0].changed_files) == 2


def test_ingest_with_vision_marks_item_ready(tmp_path: Path) -> None:
    packet_dir = _copy_review_packets(tmp_path)
    service = _service(tmp_path)

    result = service.ingest_packets(
        packet_sources=[packet_dir / "2026-02-09-al.md"],
        project_id="prj_plain",
        feature_id="feat_review_ui",
        original_vision="Provide a single table for all ready-for-review tasks.",
    )

    assert result.blocked_items == 0
    item = service.list_items()[0]
    assert item.status == ReviewStatus.READY
    assert item.project_id == "prj_plain"
    assert item.feature_id == "feat_review_ui"
    assert item.original_vision.startswith("Provide a single table")


def test_json_packet_upsert_is_stable_across_reingest(tmp_path: Path) -> None:
    packet_dir = _copy_review_packets(tmp_path)
    service = _service(tmp_path)

    first = service.ingest_packets(packet_sources=[packet_dir / "manual_items.json"])
    second = service.ingest_packets(packet_sources=[packet_dir / "manual_items.json"])

    assert first.packets_scanned == 2
    assert first.items_created == 2
    assert second.items_created == 0
    assert second.items_updated == 2
    assert len(service.list_items()) == 2


def test_review_transitions_feedback_and_instruction_access(tmp_path: Path) -> None:
    packet_dir = _copy_review_packets(tmp_path)
    service = _service(tmp_path)
    service.ingest_packets(packet_sources=[packet_dir / "manual_items.json"])

    item = service.list_items()[0]
    started = service.start_review(item.review_id)
    assert started.status == ReviewStatus.IN_REVIEW

    changed = service.request_changes(
        item.review_id,
        notes="Please add expected output details.",
        tags=["docs"],
    )
    assert changed.status == ReviewStatus.CHANGES_REQUESTED

    approved = service.approve(item.review_id, notes="Looks good now.")
    assert approved.status == ReviewStatus.APPROVED

    instruction = service.get_run_instruction(item.review_id, index=0)
    assert instruction.command
    assert instruction.cwd

    table = render_review_table(service.list_items())
    assert "Status" in table
    assert item.review_id[:8] not in table  # table is project/feature summary, not id-dump

    feedback = service.get_feedback(item.review_id)
    assert any(entry.verdict.value == "request_changes" for entry in feedback)
    assert any(entry.verdict.value == "approve" for entry in feedback)


def test_rejected_item_cannot_transition_back(tmp_path: Path) -> None:
    packet_dir = _copy_review_packets(tmp_path)
    service = _service(tmp_path)
    service.ingest_packets(packet_sources=[packet_dir / "manual_items.json"])

    item = service.list_items()[0]
    rejected = service.reject(item.review_id, notes="Out of scope for this release.")
    assert rejected.status == ReviewStatus.REJECTED

    with pytest.raises(FlowError):
        service.approve(item.review_id, notes="Trying to re-open")
