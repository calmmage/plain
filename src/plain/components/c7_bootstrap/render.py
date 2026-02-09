from __future__ import annotations

from plain.components.c7_bootstrap.models import BootstrapScenario, ScenarioRun


def render_scenarios(scenarios: list[BootstrapScenario]) -> str:
    if not scenarios:
        return "No bootstrap scenarios found"

    lines: list[str] = []
    for scenario in scenarios:
        lines.append(
            f"- {scenario.scenario_id} [{scenario.kind.value}] {scenario.title}"
        )
        lines.append(f"  tags: {', '.join(scenario.tags) if scenario.tags else '-'}")
        lines.append(f"  steps: {len(scenario.steps)}")
        lines.append(f"  description: {scenario.description}")
    return "\n".join(lines)


def render_run(run: ScenarioRun) -> str:
    lines = [
        f"run_id: {run.run_id}",
        f"scenario_id: {run.scenario_id}",
        f"mode: {run.mode.value}",
        f"status: {run.status.value}",
        f"started_at: {run.started_at.isoformat()}",
        f"finished_at: {run.finished_at.isoformat() if run.finished_at else '-'}",
        f"next_step_index: {run.next_step_index}",
        f"completed_steps: {', '.join(run.completed_steps) if run.completed_steps else '-'}",
        f"failed_step: {run.failed_step or '-'}",
        "",
        "notes:",
    ]

    lines.extend([f"- {note}" for note in run.notes] or ["- none"])
    lines.append("")
    lines.append("changed_files:")
    lines.extend([f"- {path}" for path in run.changed_files] or ["- none"])

    lines.append("")
    lines.append("step_results:")
    if run.step_results:
        for row in run.step_results:
            lines.append(f"- {row.step_id} [{row.status}] {row.summary}")
    else:
        lines.append("- none")

    return "\n".join(lines)


def render_runs(runs: list[ScenarioRun]) -> str:
    if not runs:
        return "No scenario runs found"

    lines: list[str] = []
    for run in runs:
        lines.append(
            f"- {run.run_id} [{run.status.value}] {run.scenario_id} ({run.mode.value})"
        )
        lines.append(f"  started_at: {run.started_at.isoformat()}")
        lines.append(f"  completed_steps: {len(run.completed_steps)}")
    return "\n".join(lines)
