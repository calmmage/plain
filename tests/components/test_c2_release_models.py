from pathlib import Path

import pytest

from plain.components.c2_release.models import ReleaseSpec, load_release_spec

pytest.importorskip("yaml")


def test_load_release_spec_from_fixture() -> None:
    path = Path("tests/fixtures/c2/release.yaml")
    spec = load_release_spec(path)

    assert isinstance(spec, ReleaseSpec)
    assert spec.version == "0.1.0"
    assert spec.service == "human-driven-ai-projects"
    assert spec.gates.tests is True
    assert spec.deployment.compose_file == "deploy/docker-compose.yml"
    assert spec.database.backup_required is True
    assert "telegram" in spec.launch.notify_channels
