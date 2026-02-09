from pathlib import Path

import pytest

from plain.components.c2_release.service import ReleaseService
from plain.core.models import FlowError

pytest.importorskip("yaml")


def _write_minimal_workspace(root: Path) -> None:
    (root / "tests").mkdir(parents=True, exist_ok=True)
    (root / "deploy").mkdir(parents=True, exist_ok=True)
    (root / "release").mkdir(parents=True, exist_ok=True)

    (root / "pyproject.toml").write_text(
        "\n".join(
            [
                "[project]",
                'name = "plain"',
                'version = "0.1.0"',
                "",
                "# tools",
                "ruff = true",
                "pyright = true",
            ]
        )
    )
    (root / "ruff.toml").write_text("line-length = 100\n")
    (root / "Dockerfile").write_text("FROM python:3.12-slim\n")
    (root / "deploy" / "docker-compose.yml").write_text(
        "services:\n  app:\n    image: plain:latest\n"
    )
    (root / "release" / "backup-plan.md").write_text("# Backup plan\n")
    (root / "release" / "release.yaml").write_text(
        Path("tests/fixtures/c2/release.yaml").read_text()
    )


def test_plan_and_dry_run_and_launch(tmp_path: Path) -> None:
    _write_minimal_workspace(tmp_path)
    service = ReleaseService(workspace=tmp_path)

    runbook, runbook_path = service.plan()
    assert runbook.spec.version == "0.1.0"
    assert runbook_path.exists()
    assert any(step.requires_human_approval for step in runbook.steps)

    report = service.dry_run()
    assert report.state.value == "ready_for_dry_run"
    assert report.all_critical_passed is True

    with pytest.raises(FlowError):
        service.launch(yes=False)

    launch_report, launch_paths = service.launch(yes=True)
    assert launch_report.all_critical_passed is True
    assert all(path.exists() for path in launch_paths)


def test_launch_blocked_on_failed_critical_gate(tmp_path: Path) -> None:
    _write_minimal_workspace(tmp_path)
    (tmp_path / "deploy" / "docker-compose.yml").write_text("# missing services section\n")

    service = ReleaseService(workspace=tmp_path)

    with pytest.raises(FlowError) as exc:
        service.launch(yes=True)

    assert "smoke_test" in str(exc.value)


def test_rollback_creates_incident_record(tmp_path: Path) -> None:
    _write_minimal_workspace(tmp_path)
    service = ReleaseService(workspace=tmp_path)

    incident = service.rollback()
    assert incident.exists()
    assert "rollback" in incident.name
