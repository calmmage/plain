from __future__ import annotations

import shutil
from pathlib import Path

import pytest

from plain.components.c1_flow.repository import FlowRepository
from plain.components.c1_flow.service import FlowService
from plain.components.c2_release.service import ReleaseService
from plain.components.c3_principles.repository import PrinciplesRepository
from plain.components.c3_principles.service import PrinciplesService
from plain.components.c4_daily_runner.service import DailyImplementerService
from plain.components.c5_ingest.models import IngestReviewItem, IngestedItem, ItemKind, SourceRef
from plain.components.c5_ingest.repository import ObsidianIngestRepository
from plain.components.c5_ingest.service import ObsidianIngestService
from plain.components.c6_review.models import ReviewInstruction, ReviewItem, ReviewStatus
from plain.components.c6_review.repository import ReviewRepository
from plain.components.c6_review.service import ReviewService
from plain.components.c7_bootstrap.repository import BootstrapRepository
from plain.components.c7_bootstrap.service import BootstrapService
from plain.components.c8_orchestrator.service import OrchestratorService

pytest.importorskip("yaml")


def _orchestrator(tmp_path: Path) -> OrchestratorService:
    flow_repo = FlowRepository(base_dir=tmp_path / "flows")
    flow_service = FlowService(repository=flow_repo)
    flow_service.init_project("Plain", repository_path=str(tmp_path))
    flow_service.add_feature(
        project_identifier="Plain",
        title="Workflow status",
        vision="Provide one global status command",
        feature_id="feat_workflow_status",
    )

    release_dir = tmp_path / "release"
    release_dir.mkdir(parents=True, exist_ok=True)
    (release_dir / "release.yaml").write_text(Path("tests/fixtures/c2/release.yaml").read_text())
    (release_dir / "backup-plan.md").write_text("# backup\n")
    (tmp_path / "deploy").mkdir(parents=True, exist_ok=True)
    (tmp_path / "deploy/docker-compose.yml").write_text("services:\n  app:\n    image: app:latest\n")
    (tmp_path / "pyproject.toml").write_text("[project]\nname='x'\nversion='0.0.1'\n# ruff\n# pyright\n")
    (tmp_path / "tests").mkdir(parents=True, exist_ok=True)

    principles_repo = PrinciplesRepository(
        inbox_dir=tmp_path / "principles/inbox",
        approved_dir=tmp_path / "principles/approved",
        candidates_dir=tmp_path / "principles/candidates",
        skills_dir=tmp_path / "skills/local",
    )
    principles_service = PrinciplesService(repository=principles_repo, workspace=tmp_path)
    source = tmp_path / "source.md"
    source.write_text("source")
    principles_service.capture(
        title="Keep integration concise",
        raw_quote="Prefer one status command with clear module boundaries",
        source_path=str(source),
    )

    daily_runs = tmp_path / "dev/notes/ecosystem/daily_runs"
    daily_runs.mkdir(parents=True, exist_ok=True)
    (daily_runs / "2026-02-09-al.json").write_text("{}\n")

    obsidian_repo = ObsidianIngestRepository(
        base_dir=tmp_path / "data/obsidian_ingest",
        state_path=tmp_path / "state/obsidian_state.json",
    )
    obsidian_service = ObsidianIngestService(repository=obsidian_repo, workspace=tmp_path)
    obsidian_repo.save_items(
        [
            IngestedItem(
                item_id="itm_seed",
                kind=ItemKind.IDEA,
                title="Seed idea",
                description="Seed ingest item",
                confidence=0.7,
                source_refs=[SourceRef(note_path="seed.md", note_title="seed")],
            )
        ]
    )
    obsidian_repo.save_review_queue(
        [IngestReviewItem(item_id="itm_seed", confidence=0.55, reason="seed")]
    )

    review_repo = ReviewRepository(base_dir=tmp_path / "data/review_queue")
    review_service = ReviewService(repository=review_repo, flow_service=flow_service, workspace=tmp_path)
    review_repo.save_items(
        [
            ReviewItem(
                review_id="rev_seed",
                project_id="prj_plain",
                feature_id="feat_workflow_status",
                task_key="seed",
                original_vision="Provide one global status command",
                summary="Seed review item",
                status=ReviewStatus.READY,
                run_instructions=[
                    ReviewInstruction(title="run tests", command="uv run pytest src tests", cwd=".")
                ],
                source_refs=["seed-packet.md"],
            )
        ]
    )

    scenarios_dir = tmp_path / "dev/notes/ecosystem/scenarios"
    scenarios_dir.parent.mkdir(parents=True, exist_ok=True)
    shutil.copytree(Path("dev/notes/ecosystem/scenarios"), scenarios_dir)
    bootstrap_repo = BootstrapRepository(
        scenarios_dir=scenarios_dir,
        runs_dir=tmp_path / "data/bootstrap_runs",
    )
    bootstrap_service = BootstrapService(repository=bootstrap_repo, workspace=tmp_path)

    return OrchestratorService(
        flow_service=flow_service,
        flow_repository=flow_repo,
        release_service=ReleaseService(workspace=tmp_path),
        principles_service=principles_service,
        daily_service=DailyImplementerService(workspace=tmp_path),
        obsidian_service=obsidian_service,
        obsidian_repository=obsidian_repo,
        review_service=review_service,
        review_repository=review_repo,
        bootstrap_service=bootstrap_service,
        bootstrap_repository=bootstrap_repo,
        workspace=tmp_path,
        daily_log_dir=Path("dev/notes/ecosystem/daily_runs"),
    )


def test_workflow_status_aggregates_modules(tmp_path: Path) -> None:
    service = _orchestrator(tmp_path)
    snapshot = service.workflow_status()
    by_id = {module.module_id: module for module in snapshot.modules}

    assert len(snapshot.modules) == 8
    assert by_id["m1"].details["projects"] >= 1
    assert by_id["m3"].details["principles"] >= 1
    assert by_id["m5"].details["items"] >= 1
    assert by_id["m7"].details["scenarios"] >= 6


def test_orchestrator_ingest_and_review_wrappers(tmp_path: Path) -> None:
    service = _orchestrator(tmp_path)
    daily_dir = tmp_path / "obsidian/daily"
    daily_dir.mkdir(parents=True, exist_ok=True)
    (daily_dir / "2026-02-10.md").write_text("# Daily\n\n- Feature: workflow status command")

    result = service.run_ingest(note_roots=[daily_dir], force_full_scan=True)
    assert result.notes_scanned == 1

    packet = Path("tests/fixtures/c6/review_packets/2026-02-09-al.md")
    review_result = service.ingest_review_packets(
        packet_paths=[packet],
        project_id="prj_plain",
        feature_id="feat_workflow_status",
        original_vision="Provide one global status command",
    )
    assert review_result.packets_scanned == 1
    assert service.review_queue(ready_only=True)


def test_orchestrator_bootstrap_run_and_resume(tmp_path: Path) -> None:
    service = _orchestrator(tmp_path)
    run = service.bootstrap_run("quality_gate_finish", mode="observe")
    assert run.status.value == "paused"

    resumed = service.bootstrap_resume(run.run_id, mode="interactive")
    assert resumed.status.value == "done"
