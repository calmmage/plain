from __future__ import annotations

import shutil
from pathlib import Path

import pytest

from plain.components.c7_bootstrap.models import ExecutionMode, RunStatus
from plain.components.c7_bootstrap.repository import BootstrapRepository
from plain.components.c7_bootstrap.service import BootstrapService

pytest.importorskip("yaml")


def _service(tmp_path: Path) -> BootstrapService:
    scenarios_dir = tmp_path / "scenarios"
    shutil.copytree(Path("dev/notes/ecosystem/scenarios"), scenarios_dir)
    repo = BootstrapRepository(
        scenarios_dir=scenarios_dir,
        runs_dir=tmp_path / "runs",
    )
    return BootstrapService(repository=repo, workspace=tmp_path)


def test_catalog_has_three_start_and_three_finish_scenarios(tmp_path: Path) -> None:
    service = _service(tmp_path)
    scenarios = service.list_scenarios()

    assert len(scenarios) >= 6
    start_count = len([item for item in scenarios if item.kind.value == "start"])
    finish_count = len([item for item in scenarios if item.kind.value == "finish"])
    assert start_count >= 3
    assert finish_count >= 3


def test_interactive_run_pauses_on_human_checkpoint_and_resume_completes(tmp_path: Path) -> None:
    service = _service(tmp_path)
    run = service.run_scenario(
        scenario_id="python_uv_bootstrap",
        mode=ExecutionMode.INTERACTIVE.value,
    )

    assert run.status == RunStatus.PAUSED
    assert run.next_step_index == 3
    assert run.completed_steps == ["init_repo", "sync_deps", "apply_instructions"]

    resumed = service.resume_run(run.run_id, mode=ExecutionMode.INTERACTIVE.value)
    assert resumed.status == RunStatus.DONE
    assert "confirm_bootstrap" in resumed.completed_steps


def test_observe_mode_pauses_on_human_confirmation_step(tmp_path: Path) -> None:
    service = _service(tmp_path)
    run = service.run_scenario(
        scenario_id="quality_gate_finish",
        mode=ExecutionMode.OBSERVE.value,
    )

    assert run.status == RunStatus.PAUSED
    assert run.next_step_index == 3
    assert run.completed_steps == ["lint", "typecheck", "tests"]


def test_destructive_command_blocked_without_override(tmp_path: Path) -> None:
    service = _service(tmp_path)
    dangerous = (tmp_path / "scenarios" / "dangerous_finish.yaml")
    dangerous.write_text(
        "\n".join(
            [
                "scenario_id: dangerous_finish",
                "kind: finish",
                "title: Dangerous finish",
                "description: Should fail on destructive command",
                "steps:",
                "  - step_id: wipe",
                "    title: wipe folder",
                "    primitive: shell_command",
                "    command: rm -rf ./tmp",
            ]
        )
        + "\n"
    )

    run = service.run_scenario(
        scenario_id="dangerous_finish",
        mode=ExecutionMode.OBSERVE.value,
        allow_destructive=False,
    )
    assert run.status == RunStatus.FAILED
    assert run.failed_step == "wipe"

    allowed = service.run_scenario(
        scenario_id="dangerous_finish",
        mode=ExecutionMode.OBSERVE.value,
        allow_destructive=True,
    )
    assert allowed.status == RunStatus.DONE


def test_list_runs_supports_filtering_by_scenario(tmp_path: Path) -> None:
    service = _service(tmp_path)
    a = service.run_scenario("quality_gate_finish", mode=ExecutionMode.OBSERVE.value)
    b = service.run_scenario("release_ready_finish", mode=ExecutionMode.OBSERVE.value)

    all_runs = service.list_runs()
    release_runs = service.list_runs(scenario_id="release_ready_finish")

    assert any(run.run_id == a.run_id for run in all_runs)
    assert any(run.run_id == b.run_id for run in all_runs)
    assert all(run.scenario_id == "release_ready_finish" for run in release_runs)
