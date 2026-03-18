# PRD 1: Three-phase flow and progress model

Source: `/Users/petrlavrov/calmmage/obsidian/Inbox/Human-driven AI projects.md`

Raw source excerpt (verbatim):

Lets say there are three general phases of (pet/ai) project development (but actually also anything at work)
1) make it work (build a functional demo that captures the main idea and satisfies the vision - play with it to get a feel that it's right)
2) Test (this is the "play and give feedback" part)
3) Polish (final push to convert this into an shareable artifact - whatever that entails)

Part 1 - make it work: Human describes what they want to see, ai builds it
Part 2 - ai describes how to test the pp, humans runs it and gives comments on ui and usability
Part 3 Polish - Optimize - add aliases / env / onboarding / makefile / readme / deploy

The idea is to have a data model to track the date, state and progress across that flow, and nice status visualisation for each project and each feature within them. A clean tooling to view and navigate them, easily switch across projects but recover the relevant ai conversations and continuing them.

## Goal

Create a canonical flow engine for project development where each project and each feature moves through:
- `MAKE_IT_WORK`
- `TEST`
- `POLISH`

The system must track status, evidence artifacts, linked conversations, and next actions.

## Why now

You already have working pieces:
- Scenario logic and runner ideas in `/Users/petrlavrov/work/projects/ai-scenarios/dev/3_lib/`
- Task and conversation linking in `/Users/petrlavrov/calmmage/tools/task_management/dev_task_manager/`
- Global coordination layer in `/Users/petrlavrov/calmmage/dev/notes/ecosystem/`

This PRD unifies them into a stable orchestration model.

## Scope

In scope:
- Data model for projects/features/phases.
- State transitions with validation.
- CLI to inspect and advance flow.
- Link and recover AI conversations by feature-phase.
- Optional Notion mirror interface (adapter boundary only).

Out of scope:
- Full web UI implementation (covered by Idea 6).
- Autonomous coding loops (covered by Idea 4).
- Release execution details (covered by Idea 2).

## Core object model

```python
from enum import Enum
from datetime import datetime
from pydantic import BaseModel, Field


class Phase(str, Enum):
    MAKE_IT_WORK = "make_it_work"
    TEST = "test"
    POLISH = "polish"


class PhaseStatus(str, Enum):
    TODO = "todo"
    ACTIVE = "active"
    BLOCKED = "blocked"
    DONE = "done"


class ArtifactRef(BaseModel):
    kind: str  # prd|demo|test_plan|recording|readme|deploy_note
    path: str
    note: str | None = None


class ConversationRef(BaseModel):
    client: str  # claude|codex|gemini
    session_id: str
    cwd: str
    summary: str | None = None


class PhaseRecord(BaseModel):
    phase: Phase
    status: PhaseStatus = PhaseStatus.TODO
    started_at: datetime | None = None
    finished_at: datetime | None = None
    owner: str = "human+ai"
    entry_criteria: list[str] = Field(default_factory=list)
    exit_criteria: list[str] = Field(default_factory=list)
    artifacts: list[ArtifactRef] = Field(default_factory=list)
    conversations: list[ConversationRef] = Field(default_factory=list)
    feedback: list[str] = Field(default_factory=list)


class FeatureFlow(BaseModel):
    feature_id: str
    title: str
    vision: str
    current_phase: Phase = Phase.MAKE_IT_WORK
    phases: list[PhaseRecord]
    created_at: datetime
    updated_at: datetime


class ProjectFlow(BaseModel):
    project_id: str
    project_name: str
    repository_path: str
    features: list[FeatureFlow] = Field(default_factory=list)
    tags: list[str] = Field(default_factory=list)
```

## State machine rules

Transition matrix:
- `MAKE_IT_WORK -> TEST`: requires demo artifact + "how to run" entry point.
- `TEST -> POLISH`: requires at least one human feedback cycle and accepted core UX.
- `POLISH -> DONE`: requires onboarding/readme + essential make targets + env docs + deploy note.
- Any phase can go to `BLOCKED` with explicit blocker note.
- Rollback allowed only one step back unless forced by human.

Validation function:

```python
def can_advance(feature: FeatureFlow) -> tuple[bool, str]:
    phase = feature.current_phase
    rec = next(p for p in feature.phases if p.phase == phase)

    if phase == Phase.MAKE_IT_WORK:
        has_demo = any(a.kind == "demo" for a in rec.artifacts)
        has_entry = any("entry" in (a.note or "").lower() for a in rec.artifacts)
        return (has_demo and has_entry, "need demo + entry instructions")

    if phase == Phase.TEST:
        has_feedback = len(rec.feedback) > 0
        return (has_feedback, "need at least one feedback cycle")

    if phase == Phase.POLISH:
        kinds = {a.kind for a in rec.artifacts}
        required = {"readme", "deploy_note"}
        ok = required.issubset(kinds)
        return (ok, "need readme + deploy_note")

    return (False, "invalid phase")
```

## CLI contract

New module target: `tools/task_management/dev_task_manager/` or standalone `tools/workflow/human_driven_ai/`.

Commands:
- `flow init <project_name> --repo <path>`
- `flow feature add <project> "<title>" --vision "..."`
- `flow feature show <project> <feature_id>`
- `flow phase start <project> <feature_id> <phase>`
- `flow phase advance <project> <feature_id>`
- `flow feedback add <project> <feature_id> --text "..."`
- `flow conv link <project> <feature_id> --client claude --session-id ... --cwd ...`
- `flow board <project>` (table grouped by phase/status)

## Storage design

Primary storage (local-first):
- Markdown + YAML per project flow:
  - `dev/notes/ecosystem/flows/<project_slug>.md`

Secondary storage:
- Mongo for queryable metadata and dashboards.

Optional mirror:
- Notion adapter writes project/feature/phase rows but does not own source of truth.

Example markdown shape:

```markdown
---
project_id: prj_human_ai
project_name: human-driven-ai-projects
repository_path: /Users/petrlavrov/work/projects/human-driven-ai-projects
---

## Feature f_demo_pipeline
- vision: "Build and iterate features in 3 phases"
- current_phase: test

### make_it_work
- status: done
- artifacts:
  - kind: demo
    path: docs/demos/first-run.md

### test
- status: active
- feedback:
  - "Onboarding command unclear"
```

## Conversation recovery model

Reuse existing logic in:
- `/Users/petrlavrov/calmmage/tools/task_management/dev_task_manager/handlers/conversations_find.py`
- `/Users/petrlavrov/calmmage/tools/task_management/dev_task_manager/handlers/conversations_list.py`

Attach `ConversationRef` records by feature+phase. "Resume" command should choose last active conversation for that phase.

## Board/status view

Minimum CLI table columns:
- `Feature`
- `Current phase`
- `Phase status`
- `Last update`
- `Open blockers`
- `Last conversation`

## Acceptance criteria

- Can create a project flow and at least 3 features.
- Can advance phases only when criteria are met.
- Can link/recover at least one AI conversation per phase.
- Can print board view showing all features and phase states.
- Can export a concise status snapshot for daily review.

## Implementation plan

Phase A (2-3 days):
- Implement Pydantic models.
- Implement markdown persistence.
- Implement basic CLI (`init`, `feature add`, `show`, `phase start/advance`).

Phase B (2-3 days):
- Conversation linking and resume helper integration.
- Board view and progress summaries.
- Validation rules and rollback command.

Phase C (1-2 days):
- Mongo adapter.
- Notion adapter interface (stub + one sync command).

## Risks and mitigations

- Risk: too much metadata overhead.
  - Mitigation: default minimal fields, progressively enriched.
- Risk: users skip evidence artifacts.
  - Mitigation: enforce minimal exit criteria per phase.
- Risk: conversations split across clients.
  - Mitigation: store `client` in `ConversationRef` and normalize resume command generation.

## Open questions

- Should project-level phase summary derive from all features, or be manually set?
- Should Notion mirror be append-only snapshots or upsert current state?
- Should phase transitions auto-create worksession items in `/Users/petrlavrov/calmmage/dev/notes/ecosystem/worksessions/`?
