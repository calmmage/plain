# PRD 6: Review UI for ready-for-review work

Source: `/Users/petrlavrov/calmmage/obsidian/Inbox/Human-driven AI projects.md`

Raw source excerpt (verbatim):

Review UI
- a dedicated page where we have a table of all ready-for-review
- all that “instruction of how to run that demo with entry point and a remjnder of original vision” saved and exposed clearly to jump into reviewing (and caprute comments / feedback as well)

I don't think I have a reference yet. "Task list" command, "task conversation" handler and maybe my notion databases / dashboards / views.

## Goal

Provide one review workspace where you can quickly:
- see what is ready to review,
- run/demo it with clear entry instructions,
- compare against original vision,
- leave structured feedback.

## Existing references

- `/Users/petrlavrov/calmmage/tools/task_management/dev_task_manager/handlers/task_list.py`
- `/Users/petrlavrov/calmmage/tools/task_management/dev_task_manager/handlers/conversations_list.py`
- `/Users/petrlavrov/calmmage/tools/task_management/dev_task_manager/handlers/conversations_find.py`
- `/Users/petrlavrov/calmmage/dev/notes/ecosystem/prds/human-driven-ai-projects/04-daily-implementation-automation.md`

## Scope

In scope:
- Review queue data model.
- Table UI spec.
- Review actions and state transitions.
- Feedback capture linked to feature and phase.

Out of scope:
- Full PM suite; this is execution review only.

## Review item model

```python
from datetime import datetime
from pydantic import BaseModel, Field


class ReviewStatus(str, Enum):
    READY = "ready"
    IN_REVIEW = "in_review"
    CHANGES_REQUESTED = "changes_requested"
    APPROVED = "approved"
    REJECTED = "rejected"


class ReviewInstruction(BaseModel):
    title: str
    command: str
    cwd: str
    expected_result: str | None = None


class ReviewItem(BaseModel):
    review_id: str
    project_id: str
    feature_id: str
    task_key: str | None = None
    original_vision: str
    summary: str
    status: ReviewStatus = ReviewStatus.READY
    run_instructions: list[ReviewInstruction] = Field(default_factory=list)
    changed_files: list[str] = Field(default_factory=list)
    source_refs: list[str] = Field(default_factory=list)
    conversation_refs: list[str] = Field(default_factory=list)
    created_at: datetime
    updated_at: datetime
```

## UI layout

Primary table columns:
- `Status`
- `Project`
- `Feature`
- `Summary`
- `Original vision`
- `How to run`
- `Changed files`
- `Updated`

Detail panel tabs:
- Overview
- Run instructions
- Diff/files
- Conversations
- Feedback history

## Main actions

- `Start review`
- `Run demo` (copies command or runs in terminal integration)
- `Add feedback`
- `Approve`
- `Request changes`
- `Open source` (file path links)

Feedback schema:

```python
class FeedbackEntry(BaseModel):
    review_id: str
    author: str = "human"
    verdict: str  # approve|request_changes|question
    notes: str
    tags: list[str] = Field(default_factory=list)
    created_at: datetime
```

## Data sources

Ingest review items from:
- daily implementation automation output packets
- manual task submissions
- release dry-run outputs (optional)

## Queue population protocol

A job or command writes review packets to:
- `/Users/petrlavrov/calmmage/dev/notes/ecosystem/review_packets/`

UI service ingests packets and upserts queue rows.

## Vision reminder requirement

Each review item must include a concise `original_vision` field.
If missing, item cannot enter `READY` state.

## Integration with task/conversation tools

- `task conv find` for session resume links.
- `task list` fields as baseline status metadata.
- feature-phase records from PRD 1 as parent context.

## Notion compatibility mode

Optional:
- Mirror queue to Notion database with same fields.
- Keep local storage as source of truth.

## Acceptance criteria

- Can list all ready review items in one table.
- Every item has runnable entry instructions.
- Reviewer can record feedback and change item status.
- Reviewer can open related conversations and files quickly.
- Items missing original vision are blocked from READY.

## Implementation plan

Phase A:
- Define queue schema + local storage.
- Build CLI view and status-change commands.

Phase B:
- Build minimal web table UI.
- Add detail drawer and feedback form.

Phase C:
- Add Notion mirror adapter.
- Add metrics: throughput, average review time, reject reasons.

## Risks and mitigations

- Risk: stale or broken run commands.
  - Mitigation: auto-verify commands before marking READY.
- Risk: review overload.
  - Mitigation: prioritization and batching by project/feature.
- Risk: feedback gets fragmented across tools.
  - Mitigation: central feedback schema and single queue id.

## Open questions

- UI first delivery preference: terminal TUI or web app?
- Should review items auto-expire after N days?
- Should approval auto-trigger polish phase updates?
