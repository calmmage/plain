# plain

`plain` is an incremental implementation of the "human-driven AI projects" PRD stack.

## Setup

```shell
pre-commit install
```

## C1: Three-Phase Flow Engine

The c1 layer tracks project features across:
- `make_it_work`
- `test`
- `polish`

Core model shape:
- `ProjectFlow`: project identity, repo path, feature list, tags, timestamps
- `FeatureFlow`: feature identity, vision, current phase, timestamps
- `PhaseRecord`: status, artifacts, feedback, blockers, conversation links
- structured phase metadata per status:
  - `code_links`
  - `entry_points`
  - `explanations`

Persistence:
- markdown + YAML frontmatter per project
- path: `dev/notes/ecosystem/flows/<project_slug>.md`

CLI (via `src/main.py`):

```bash
uv run python src/main.py init <project_name> --repo <path>
uv run python src/main.py feature add <project> "<title>" --vision "..."
uv run python src/main.py feature show <project> <feature_id>
uv run python src/main.py phase start <project> <feature_id> <phase>
uv run python src/main.py phase advance <project> <feature_id>
uv run python src/main.py feedback add <project> <feature_id> --text "..."
uv run python src/main.py conv link <project> <feature_id> --client codex --session-id ... --cwd ...
uv run python src/main.py board <project>
uv run python src/main.py snapshot <project>
```

Additional c1 helper commands:
- `artifact add` to attach evidence for advancement checks
- `meta add` to store per-phase links/entrypoints/explanations
- `conv resume` to print latest resume command per feature-phase

Demo:

```bash
make demo-c1
```

Details: `dev/notes/demos/c1.md`.

## C2: Release Flow

The c2 layer adds release protocol scaffolding from `release/release.yaml`:
- release runbook generation
- gate-based dry-run checks
- launch blocking on failed critical gates
- explicit `--yes` approval for launch
- rollback incident record generation

CLI (via module wrapper):

```bash
uv run python -m tools.release.cli plan --spec release/release.yaml
uv run python -m tools.release.cli dry-run --spec release/release.yaml
uv run python -m tools.release.cli launch --spec release/release.yaml --yes
uv run python -m tools.release.cli rollback --spec release/release.yaml
```

Make targets:
- `release-plan`
- `release-dry-run`
- `release-launch`
- `release-rollback`
- `demo-c2`

Release baseline files:
- `release/release.yaml`
- `release/backup-plan.md`
- `deploy/docker-compose.yml`

Demo:

```bash
make demo-c2
```

Details: `dev/notes/demos/c2.md`.

## C3: Principles to Skills Protocol

The c3 layer captures repeated guidance as principles and promotes them to reusable skill assets.

Capabilities:
- principle capture with structured metadata and examples
- promotion flow: principle note -> skill candidate -> generated `SKILL.md`
- rubric-based `test-skill` scoring
- explicit `approve-skill` gate
- deployment of approved principle bundle into instruction files (`AGENTS.md`, `CLAUDE.md`, `GEMINI.md`)

CLI (via workflow wrapper):

```bash
uv run python -m tools.workflow.principles.cli capture --title "..." --raw "..." --source /path/file.md
uv run python -m tools.workflow.principles.cli list --status draft
uv run python -m tools.workflow.principles.cli promote <principle_id> --skill-name concise-coordinator --scope coding
uv run python -m tools.workflow.principles.cli test-skill <candidate_id> --prompt "..."
uv run python -m tools.workflow.principles.cli approve-skill <candidate_id>
uv run python -m tools.workflow.principles.cli deploy --target AGENTS.md --target CLAUDE.md --target GEMINI.md
```

Storage layout:
- `dev/notes/ecosystem/principles/inbox/`
- `dev/notes/ecosystem/principles/approved/`
- `dev/notes/ecosystem/principles/candidates/`
- `skills/local/<skill-name>/SKILL.md`

Demo:

```bash
make demo-c3
```

Details: `dev/notes/demos/c3.md`.

## C4: Daily Feature Implementer

The c4 layer runs one focused implementation cycle with deterministic selection and review artifacts.

Capabilities:
- candidate pool parsing from markdown/json task sources
- task scoring with auditable reasons
- deterministic workspace choice (`main_repo`, `git_worktree`, `new_repo_from_template`)
- context enrichment pipeline (collect, dedupe, classify origin, summarize)
- review packet + execution log generation with safety rails

CLI (via workflow wrapper):

```bash
uv run python -m tools.workflow.daily_runner.cli score --task-source <path>
uv run python -m tools.workflow.daily_runner.cli run \
  --task-source <path> \
  --context-source <path> \
  --repo-path <path> \
  --client codex
```

Sample daily inputs:
- `dev/notes/ecosystem/daily_inputs/tasks_sample.md`
- `dev/notes/ecosystem/daily_inputs/obsidian_context.md`
- `dev/notes/ecosystem/daily_inputs/telegram_context.json`
- `dev/notes/ecosystem/daily_inputs/bookmarks_context.json`

Demo:

```bash
make demo-c4
```

Details: `dev/notes/demos/c4.md`.

## C5: Obsidian Ideas Ingest + Backlinks

The c5 layer ingests changed Obsidian notes into a structured entity store for review and downstream automation.

Capabilities:
- incremental changed-note scan using persisted file hash cursor
- hybrid extraction (note title + checklist bullets)
- default folder-to-kind mapping:
  - `daily` -> `idea`
  - `dumps` -> `idea`
  - `workalongs` -> `experiment`
  - `preproject` -> `preproject`
- explicit backlink preservation on every extracted item (`source_refs`)
- low-confidence review queue + duplicate candidate tracking
- downstream query/update APIs:
  - `get_items`
  - `get_item_with_sources`
  - `get_pending_review_items`
  - `approve_item`
  - `merge_items`
  - `reclassify_item`

CLI (via workflow wrapper):

```bash
uv run python -m tools.workflow.obsidian_ingest.cli run --note-root <path>
uv run python -m tools.workflow.obsidian_ingest.cli list --kind feature --min-confidence 0.6
uv run python -m tools.workflow.obsidian_ingest.cli get <item_id>
uv run python -m tools.workflow.obsidian_ingest.cli pending
uv run python -m tools.workflow.obsidian_ingest.cli approve <item_id>
uv run python -m tools.workflow.obsidian_ingest.cli merge <primary_id> <duplicate_id>
uv run python -m tools.workflow.obsidian_ingest.cli reclassify <item_id> project
```

Storage layout:
- `data/obsidian_ingest/items.json`
- `data/obsidian_ingest/review_queue.json`
- `data/obsidian_ingest/duplicates.json`
- `data/obsidian_ingest/runs/*.json`
- `dev/notes/ecosystem/state/obsidian_ingest_state.json`

Demo:

```bash
make demo-c5
```

Details: `dev/notes/demos/c5.md`.

## C6: Review Queue UI (CLI-first)

The c6 layer provides one review workspace for ready work, including run instructions, vision reminder, source links, and feedback history.

Capabilities:
- review queue schema with status lifecycle:
  - `ready`
  - `in_review`
  - `changes_requested`
  - `approved`
  - `rejected`
- ingest from review packet sources (`.md` and `.json`) with upsert behavior
- READY gating rule:
  - if `original_vision` is missing, item is blocked from `ready` and marked `changes_requested`
- review actions:
  - `start`
  - `approve`
  - `request-changes`
  - `reject`
  - `feedback`
- table/detail CLI output with:
  - status/project/feature/summary
  - run instruction commands (`command` + `cwd`)
  - changed files and source refs
  - feedback history

CLI (via workflow wrapper):

```bash
uv run python -m tools.workflow.review_ui.cli ingest --packet-path <path>
uv run python -m tools.workflow.review_ui.cli list --ready-only
uv run python -m tools.workflow.review_ui.cli show <review_id>
uv run python -m tools.workflow.review_ui.cli start <review_id>
uv run python -m tools.workflow.review_ui.cli run <review_id> --index 1
uv run python -m tools.workflow.review_ui.cli feedback <review_id> --verdict question --notes "..."
uv run python -m tools.workflow.review_ui.cli approve <review_id> --notes "..."
uv run python -m tools.workflow.review_ui.cli request-changes <review_id> --notes "..."
```

Storage layout:
- `data/review_queue/items.json`
- `data/review_queue/feedback.json`

Demo:

```bash
make demo-c6
```

Details: `dev/notes/demos/c6.md`.

## C7: Bootstrap Scenarios (Start/Finish)

The c7 layer adds a hard-coded scenario catalog and safe runner for project bootstrap and finish workflows.

Capabilities:
- scenario registry loaded from versioned YAML files:
  - `dev/notes/ecosystem/scenarios/*.yaml`
- catalog includes 6 baseline scenarios:
  - start: `python_uv_bootstrap`, `nextjs_bootstrap`, `repo_hygiene_bootstrap`
  - finish: `quality_gate_finish`, `test_generation_finish`, `release_ready_finish`
- execution modes:
  - `interactive`: pauses at human checkpoints
  - `observe`: runs unattended until blocker/checkpoint
- safety rails:
  - destructive command blocking by default
  - step budget and wall-time budget
  - per-step run records and status notes
- run persistence and resume:
  - run records stored under `data/bootstrap_runs/*.json`
  - paused runs resumable by `run_id`

CLI (via workflow wrapper):

```bash
uv run python -m tools.workflow.bootstrap.cli list
uv run python -m tools.workflow.bootstrap.cli run quality_gate_finish --observe
uv run python -m tools.workflow.bootstrap.cli resume <run_id> --interactive
uv run python -m tools.workflow.bootstrap.cli runs --scenario-id quality_gate_finish
```

Demo:

```bash
make demo-c7
```

Details: `dev/notes/demos/c7.md`.
