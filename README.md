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
