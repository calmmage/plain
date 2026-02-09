from pathlib import Path

import pytest

from plain.components.c1_flow.repository import FlowRepository, split_frontmatter
from plain.core.models import ProjectFlow

pytest.importorskip("yaml")


def test_load_fixture_and_roundtrip(tmp_path: Path) -> None:
    fixture_path = Path("tests/fixtures/c1/sample_project_flow.md")
    content = fixture_path.read_text()
    payload, _ = split_frontmatter(content)

    project = ProjectFlow.from_dict(payload)
    assert project.project_name == "human-driven-ai-projects"
    assert len(project.features) == 1

    repo = FlowRepository(base_dir=tmp_path / "flows")
    path = repo.save(project)
    loaded = repo.load("human-driven-ai-projects")

    assert path.exists()
    assert loaded.project_id == project.project_id
    assert loaded.features[0].feature_id == "feat_three_phase_cli"
