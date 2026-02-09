from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Iterable

from plain.components.c7_bootstrap.models import (
    BootstrapScenario,
    ExecutionMode,
    RunStatus,
    ScenarioKind,
    ScenarioRun,
    ScenarioStep,
    StepPrimitive,
    StepRunRecord,
    utc_now,
)
from plain.components.c7_bootstrap.repository import BootstrapRepository
from plain.core.models import FlowError


@dataclass(slots=True)
class StepExecution:
    status: str
    summary: str
    changed_files: list[str]


@dataclass(slots=True)
class BootstrapService:
    repository: BootstrapRepository
    workspace: Path = Path(".")

    @classmethod
    def create_default(cls) -> "BootstrapService":
        return cls(repository=BootstrapRepository())

    def list_scenarios(
        self,
        kind: str | None = None,
        tag: str | None = None,
    ) -> list[BootstrapScenario]:
        scenarios = self.repository.load_scenarios()
        if kind:
            target_kind = ScenarioKind(kind)
            scenarios = [item for item in scenarios if item.kind == target_kind]
        if tag:
            needle = tag.lower().strip()
            scenarios = [
                item for item in scenarios if any(t.lower() == needle for t in item.tags)
            ]
        return sorted(scenarios, key=lambda item: (item.kind.value, item.scenario_id))

    def get_scenario(self, scenario_id: str) -> BootstrapScenario:
        for item in self.repository.load_scenarios():
            if item.scenario_id == scenario_id:
                return item
        raise FlowError(f"Bootstrap scenario not found: {scenario_id}")

    def run_scenario(
        self,
        scenario_id: str,
        mode: str = ExecutionMode.INTERACTIVE.value,
        max_steps: int = 40,
        max_wall_time_sec: int = 1800,
        allow_destructive: bool = False,
    ) -> ScenarioRun:
        scenario = self.get_scenario(scenario_id)
        run = ScenarioRun(
            run_id=self._next_run_id(scenario_id),
            scenario_id=scenario_id,
            mode=ExecutionMode(mode),
            status=RunStatus.RUNNING,
            started_at=utc_now(),
            next_step_index=0,
        )
        run = self._continue_run(
            run=run,
            scenario=scenario,
            max_steps=max_steps,
            max_wall_time_sec=max_wall_time_sec,
            allow_destructive=allow_destructive,
        )
        self.repository.save_run(run)
        return run

    def resume_run(
        self,
        run_id: str,
        mode: str | None = None,
        max_steps: int = 40,
        max_wall_time_sec: int = 1800,
        allow_destructive: bool = False,
    ) -> ScenarioRun:
        run = self.repository.load_run(run_id)
        if mode:
            run.mode = ExecutionMode(mode)

        if run.status == RunStatus.DONE:
            return run
        if run.status == RunStatus.FAILED:
            raise FlowError(f"Cannot resume failed run: {run_id}")

        scenario = self.get_scenario(run.scenario_id)
        run = self._apply_resume_checkpoint_confirmation(run, scenario)
        run = self._continue_run(
            run=run,
            scenario=scenario,
            max_steps=max_steps,
            max_wall_time_sec=max_wall_time_sec,
            allow_destructive=allow_destructive,
        )
        self.repository.save_run(run)
        return run

    def list_runs(self, scenario_id: str | None = None) -> list[ScenarioRun]:
        runs = self.repository.list_runs()
        if scenario_id:
            runs = [item for item in runs if item.scenario_id == scenario_id]
        return runs

    def _continue_run(
        self,
        run: ScenarioRun,
        scenario: BootstrapScenario,
        max_steps: int,
        max_wall_time_sec: int,
        allow_destructive: bool,
    ) -> ScenarioRun:
        total_steps_executed = len(run.completed_steps)

        while run.next_step_index < len(scenario.steps):
            if total_steps_executed >= max_steps:
                run.status = RunStatus.PAUSED
                run.notes.append(f"Paused by step budget: {max_steps}")
                return run

            elapsed = utc_now() - run.started_at
            if elapsed > timedelta(seconds=max_wall_time_sec):
                run.status = RunStatus.PAUSED
                run.notes.append(f"Paused by wall-time budget: {max_wall_time_sec}s")
                return run

            step = scenario.steps[run.next_step_index]
            started_at = utc_now()
            execution = self._execute_step(
                step=step,
                mode=run.mode,
                allow_destructive=allow_destructive,
            )
            finished_at = utc_now()

            run.step_results.append(
                StepRunRecord(
                    step_id=step.step_id,
                    status=execution.status,
                    summary=execution.summary,
                    started_at=started_at,
                    finished_at=finished_at,
                )
            )

            if execution.status == "completed":
                run.completed_steps.append(step.step_id)
                run.changed_files.extend(execution.changed_files)
                run.next_step_index += 1
                total_steps_executed += 1
                continue

            if execution.status == "paused":
                run.status = RunStatus.PAUSED
                run.notes.append(execution.summary)
                return run

            run.status = RunStatus.FAILED
            run.failed_step = step.step_id
            run.finished_at = utc_now()
            run.notes.append(execution.summary)
            return run

        run.status = RunStatus.DONE
        run.finished_at = utc_now()
        run.changed_files = sorted(set(run.changed_files))
        return run

    def _apply_resume_checkpoint_confirmation(
        self,
        run: ScenarioRun,
        scenario: BootstrapScenario,
    ) -> ScenarioRun:
        if run.mode != ExecutionMode.INTERACTIVE:
            return run
        if run.status != RunStatus.PAUSED:
            return run
        if run.next_step_index >= len(scenario.steps):
            return run

        step = scenario.steps[run.next_step_index]
        if not (step.requires_human or step.primitive == StepPrimitive.HUMAN_CONFIRMATION):
            return run

        now = utc_now()
        run.step_results.append(
            StepRunRecord(
                step_id=step.step_id,
                status="completed",
                summary=f"Human checkpoint confirmed on resume: {step.step_id}",
                started_at=now,
                finished_at=now,
            )
        )
        run.completed_steps.append(step.step_id)
        run.next_step_index += 1
        run.notes.append(f"Confirmed checkpoint on resume: {step.step_id}")
        run.status = RunStatus.RUNNING
        run.finished_at = None
        return run

    def _execute_step(
        self,
        step: ScenarioStep,
        mode: ExecutionMode,
        allow_destructive: bool,
    ) -> StepExecution:
        if mode == ExecutionMode.INTERACTIVE and (
            step.requires_human or step.primitive == StepPrimitive.HUMAN_CONFIRMATION
        ):
            return StepExecution(
                status="paused",
                summary=f"Awaiting human confirmation: {step.step_id}",
                changed_files=[],
            )

        if mode == ExecutionMode.OBSERVE and step.primitive == StepPrimitive.HUMAN_CONFIRMATION:
            return StepExecution(
                status="paused",
                summary=f"Observe mode paused on human checkpoint: {step.step_id}",
                changed_files=[],
            )

        if step.command and _looks_destructive(step.command) and not allow_destructive:
            return StepExecution(
                status="failed",
                summary=f"Blocked destructive command in step {step.step_id}",
                changed_files=[],
            )

        if step.command:
            changed_files = _extract_changed_files(step.command)
            return StepExecution(
                status="completed",
                summary=f"Simulated command: {step.command}",
                changed_files=changed_files,
            )

        if step.instruction:
            return StepExecution(
                status="completed",
                summary=f"Simulated instruction: {step.instruction}",
                changed_files=[],
            )

        return StepExecution(
            status="completed",
            summary=f"No-op step: {step.step_id}",
            changed_files=[],
        )

    @staticmethod
    def _next_run_id(scenario_id: str) -> str:
        stamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S_%f")
        return f"run_{scenario_id}_{stamp}"


def _looks_destructive(command: str) -> bool:
    lowered = command.lower()
    patterns = [
        r"\brm\s+-rf\b",
        r"\bgit\s+reset\s+--hard\b",
        r"\bgit\s+checkout\s+--\b",
        r"\bmkfs\b",
        r":\s*>\s*/",
    ]
    return any(re.search(pattern, lowered) for pattern in patterns)


def _extract_changed_files(command: str) -> list[str]:
    tokens = re.findall(r"[A-Za-z0-9_./-]+", command)
    out: list[str] = []
    for token in tokens:
        if "/" not in token:
            continue
        if token.endswith((".py", ".md", ".json", ".yaml", ".yml", ".toml", ".tsx", ".ts", ".js", ".jsx")):
            out.append(token)
    return sorted(set(out))
