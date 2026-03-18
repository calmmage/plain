# PRD 8: Integrated system design for human-driven AI projects

Source set:
- `/Users/petrlavrov/calmmage/obsidian/Inbox/Human-driven AI projects.md`
- PRD 1..7 in this folder

## Goal

Define one coherent operating system where idea intake, feature execution, review, release, and knowledge codification reinforce each other.

## System summary

The integrated loop has eight modules:
- M1: Three-phase flow engine (project/feature state)
- M2: Release flow executor
- M3: Principles->skills capture
- M4: Daily feature implementer
- M5: Obsidian ingestion and entity store
- M6: Review UI queue
- M7: Bootstrap scenario runner
- M8: Coordination layer (`dev/notes/ecosystem`)

## Operating loop

Daily cadence:
1. M5 ingests new notes and updates entities.
2. M4 selects one task/feature and runs implementation cycle.
3. M6 receives review packet and waits for human decision.
4. M1 updates feature phase based on review outcome.
5. M3 captures reusable principles from session outcomes.

Weekly cadence:
1. M7 runs start/finish bootstrap scenarios where needed.
2. M2 runs release dry-runs for near-ready features.
3. M8 updates ecosystem worksession and priorities.

## Canonical entities

```python
class Project(BaseModel):
    project_id: str
    name: str

class Feature(BaseModel):
    feature_id: str
    project_id: str
    title: str
    phase: str  # make_it_work|test|polish

class Task(BaseModel):
    task_key: str
    feature_id: str | None = None
    status: str

class ReviewPacket(BaseModel):
    review_id: str
    feature_id: str
    task_key: str | None
    verdict: str | None = None

class Principle(BaseModel):
    principle_id: str
    derived_from_review_id: str | None = None
```

## Data ownership model

Source of truth by domain:
- Coordination pointers: `dev/notes/ecosystem/*`
- Feature flow states: flow storage from PRD 1
- Review packets: local review queue storage from PRD 6
- Extracted knowledge entities: ingestion store from PRD 5
- Skills/principles: principle registry from PRD 3

Mirror targets:
- Notion (optional; never source of truth)

## Cross-module contracts

M5 -> M4
- provides ranked context snippets and candidate feature signals.

M4 -> M6
- emits review packet with run instructions and changed files.

M6 -> M1
- emits verdict (`approved`, `changes_requested`) affecting phase progress.

M1 -> M2
- if feature enters `POLISH` and gates pass, feature becomes release candidate.

M6 + M2 -> M3
- derive principles from repeated review/release findings.

M7 -> M1/M4
- creates ready environments and baseline workflows for faster execution.

## Event model

Standard events:
- `idea.ingested`
- `feature.selected`
- `implementation.completed`
- `review.requested`
- `review.approved`
- `review.changes_requested`
- `phase.advanced`
- `release.dry_run.completed`
- `principle.captured`
- `skill.approved`

Each event payload includes:
- `timestamp`
- `project_id`
- `feature_id` (if applicable)
- `source_refs`

## Minimal architecture

- CLI-first orchestration.
- Local markdown/json stores + optional Mongo index.
- Reusable adapters for Notion/Telegram.

Component map:
- `tools/automations/new_local_job_runner/` for scheduled execution.
- `tools/task_management/dev_task_manager/` for task and conversation integration.
- `tools/automations/obsidian_sorter/` + `calmlib/obsidian/*` for ingestion.
- New `tools/workflow/human_driven_ai/` module for integrated commands.

## Unified command surface

- `workflow ingest` -> run M5
- `workflow run-daily` -> run M4
- `workflow review queue` -> open M6 queue
- `workflow phase board` -> M1 status board
- `workflow release dry-run` -> M2
- `workflow principles capture` -> M3
- `workflow bootstrap run <scenario>` -> M7
- `workflow status` -> global summary across M1..M7

## End-to-end acceptance scenario

1. New idea is written in Obsidian daily note.
2. Ingestion job creates feature candidate with backlink.
3. Daily implementer picks feature task and opens worktree.
4. AI implements and emits review packet.
5. Review UI shows clear run instructions and original vision.
6. Human approves; feature phase advances from `MAKE_IT_WORK` to `TEST`.
7. Repeated review feedback yields a new principle.
8. Principle is promoted to skill and deployed into instruction files.
9. Release dry-run passes when feature reaches polish-ready.

## KPI set

Flow KPIs:
- idea-to-first-implementation latency
- phase transition velocity
- review turnaround time
- changes-requested ratio

Quality KPIs:
- % review packets with valid run instructions
- % features with complete source backlinks
- regression rate after approval

Knowledge KPIs:
- principles captured per week
- approved skills reused per week

## Rollout plan

Stage 1 (foundation):
- Implement M1, M4, M6 minimal integration.

Stage 2 (knowledge loop):
- Integrate M5 and M3.

Stage 3 (hardening):
- Integrate M2 and M7.
- Add global status command and weekly summary reports.

## Risks and mitigations

- Risk: too many moving parts and context switching.
  - Mitigation: strict pointer-only coordination docs + clear command surface.
- Risk: duplicated data across stores.
  - Mitigation: explicit ownership and id mapping.
- Risk: automation overreach.
  - Mitigation: mandatory human checkpoints in review/release.

## Open decisions

- Single repo vs multi-repo default for new features?
- Notion mirror now or after local loop stabilizes?
- Which module should own identity generation (`project_id`, `feature_id`)?

## Recommended first implementation sequence

1. Build `workflow status` and `workflow run-daily` wrappers over existing tools.
2. Add review packet schema and queue ingestion.
3. Add phase transition command with validation gates.
4. Add ingestion-to-feature linking.
5. Add principle capture from review outcomes.
