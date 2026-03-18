# PRD 7: Hard-coded bootstrap scenarios for project start/finish

Source: `/Users/petrlavrov/calmmage/obsidian/Inbox/Human-driven AI projects.md`

Raw source excerpt (verbatim):

A collection of hard-code scenarios that bootstrap start or finish of a project
For example
- Initial uv env setup with personal lib imports and downloads
- Initial nextjs project setup with ai rules and env presets / visual design flow
- A style guide fixer / run pyright and fix all issues one by one
- A test generation agent
- a test stand / mock data setup
Ability to trigger that by a command and launch an interactive session with a user / just observe ai running in a loop fixing stuff

References: my "nmp" alias - "dev project manager" and my "fix_repo" command - repo_fixer

## Goal

Create a reusable scenario catalog that can bootstrap predictable project start/finish workflows with one command.

## Existing references

- `/Users/petrlavrov/calmmage/tools/task_management/dev_project_manager/pm_cli.py`
- `/Users/petrlavrov/calmmage/tools/task_management/dev_project_manager/project_manager.py`
- `/Users/petrlavrov/calmmage/tools/misc/repo_fixer/repo_fixer.py`
- `/Users/petrlavrov/calmmage/tools/task_management/dev_project_manager/templates/mini-botspot-template/`

## Scope

In scope:
- Scenario registry and execution protocol.
- Start scenarios and finish scenarios.
- Interactive mode and unattended mode.
- Shared step primitives (env, lint, test, docs, release prep).

Out of scope:
- Arbitrary free-form autonomous loops without budget constraints.

## Scenario catalog v1

Start scenarios:
- `python_uv_bootstrap`
- `nextjs_bootstrap`
- `repo_hygiene_bootstrap`

Finish scenarios:
- `quality_gate_finish`
- `test_generation_finish`
- `release_ready_finish`

## Scenario model

```python
from pydantic import BaseModel, Field
from typing import Literal


class ScenarioStep(BaseModel):
    step_id: str
    title: str
    command: str | None = None
    instruction: str | None = None
    requires_human: bool = False
    timeout_sec: int = 600


class BootstrapScenario(BaseModel):
    scenario_id: str
    kind: Literal["start", "finish"]
    title: str
    description: str
    tags: list[str] = Field(default_factory=list)
    steps: list[ScenarioStep]
```

## Execution modes

- `interactive`: pause at checkpoints, ask user to approve/skip.
- `observe`: AI executes allowed steps with logs; prompts user only on blockers.

Command interface:
- `bootstrap list`
- `bootstrap run <scenario_id> --interactive`
- `bootstrap run <scenario_id> --observe`
- `bootstrap resume <run_id>`

## Scenario definitions

Stored as versioned yaml:
- `/Users/petrlavrov/calmmage/dev/notes/ecosystem/scenarios/*.yaml`

Example scenario:

```yaml
scenario_id: python_uv_bootstrap
kind: start
title: Python UV bootstrap
steps:
  - step_id: init_repo
    title: Initialize uv project
    command: "uv init"
  - step_id: sync_deps
    title: Sync dependencies
    command: "uv sync"
  - step_id: apply_rules
    title: Deploy AI instructions
    command: "typer tools/automations/ai_instructions_composer/cli.py run deploy-all"
  - step_id: run_fix_repo
    title: Apply repo baseline
    command: "typer tools/misc/repo_fixer/repo_fixer.py run run-all"
```

## Step primitives

Primitive step types:
- `shell_command`
- `agent_prompt`
- `file_template_apply`
- `human_confirmation`
- `validation_check`

This keeps scenarios composable and safe.

## Policy and safety

- Deny destructive commands unless explicit confirmation.
- Enforce per-step timeout.
- Enforce run budget (max steps, max wall time).
- Record every step status and output summary.

Run record model:

```python
class ScenarioRun(BaseModel):
    run_id: str
    scenario_id: str
    status: str  # running|paused|done|failed
    started_at: datetime
    finished_at: datetime | None = None
    completed_steps: list[str] = []
    failed_step: str | None = None
    notes: list[str] = []
```

## Integration points

- Use `dev_project_manager` for new project/mini-project destination logic.
- Use `repo_fixer` for hygiene and baseline upgrades.
- Use PRD 3 principles system to improve scenarios over time.
- Feed outputs to PRD 6 review queue.

## Acceptance criteria

- At least 3 start and 3 finish scenarios runnable.
- Scenario run can be paused and resumed by run id.
- Each run produces concise summary and changed file list.
- Interactive mode asks for confirmation at checkpoint steps.
- Observe mode runs unattended within explicit safety rails.

## Implementation plan

Phase A:
- Scenario schema + parser + runner.
- `bootstrap list/run/resume` CLI commands.

Phase B:
- Implement initial catalog using existing `nmp` and `fix_repo` workflows.
- Add step primitive adapters.

Phase C:
- Add run history storage and quality metrics.
- Add scenario recommendation by project type.

## Risks and mitigations

- Risk: scenario drift from real project conventions.
  - Mitigation: central versioned scenario catalog + review cadence.
- Risk: too many prompts in interactive mode.
  - Mitigation: critical checkpoints only.
- Risk: unsafe command execution.
  - Mitigation: allowlist + explicit confirmation gates.

## Open questions

- Should scenarios be globally shared or project-local first?
- Should AI be allowed to modify scenario definitions during runs?
- Preferred default mode: interactive or observe?
