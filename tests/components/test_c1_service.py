from pathlib import Path

import pytest

from plain.components.c1_flow.repository import FlowRepository
from plain.components.c1_flow.service import FlowService
from plain.core.models import FlowError, Phase

pytest.importorskip("yaml")


def test_service_roundtrip_and_resume(tmp_path: Path) -> None:
    repo = FlowRepository(base_dir=tmp_path / "flows")
    service = FlowService(repository=repo)

    project = service.init_project(
        project_name="human-driven-ai-projects",
        repository_path="/Users/petrlavrov/work/projects/plain",
        tags=["workflow", "prd1"],
    )
    assert project.project_id == "prj_human_driven_ai_projects"

    feature = service.add_feature(
        "human-driven-ai-projects",
        "Flow CLI",
        "Implement project/feature phase management",
    )

    service.add_artifact(
        "human-driven-ai-projects",
        feature.feature_id,
        kind="demo",
        path="dev/notes/demos/c1.md",
        note="entry: make demo-c1",
    )
    service.add_phase_metadata(
        "human-driven-ai-projects",
        feature.feature_id,
        entry_point="make demo-c1",
        code_link="src/plain/cli.py",
        explanation="CLI command set for c1",
    )

    started = service.phase_start(
        "human-driven-ai-projects",
        feature.feature_id,
        Phase.MAKE_IT_WORK.value,
    )
    assert started.current_phase == Phase.MAKE_IT_WORK

    advanced = service.phase_advance("human-driven-ai-projects", feature.feature_id)
    assert advanced.current_phase == Phase.TEST

    service.add_feedback("human-driven-ai-projects", feature.feature_id, "UX looks clear")
    service.phase_advance("human-driven-ai-projects", feature.feature_id)

    service.add_artifact(
        "human-driven-ai-projects",
        feature.feature_id,
        kind="readme",
        path="README.md",
    )
    service.add_artifact(
        "human-driven-ai-projects",
        feature.feature_id,
        kind="deploy_note",
        path="dev/notes/deploy/c1.md",
    )

    service.link_conversation(
        "human-driven-ai-projects",
        feature.feature_id,
        client="codex",
        session_id="abc-123",
        cwd="/Users/petrlavrov/work/projects/plain",
        summary="Review polish checklist",
    )

    command = service.resume_command("human-driven-ai-projects", feature.feature_id)
    assert "codex --resume abc-123" in command

    rows = service.board_rows("human-driven-ai-projects")
    assert rows[0]["Feature"] == feature.feature_id

    snapshot = service.snapshot("human-driven-ai-projects")
    assert "project=human-driven-ai-projects" in snapshot


def test_resume_requires_linked_conversation(tmp_path: Path) -> None:
    repo = FlowRepository(base_dir=tmp_path / "flows")
    service = FlowService(repository=repo)

    service.init_project("Demo", "/tmp/demo")
    feature = service.add_feature("Demo", "Simple", "Simple vision")

    with pytest.raises(FlowError):
        service.resume_command("Demo", feature.feature_id)
