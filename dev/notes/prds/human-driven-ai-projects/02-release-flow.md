# PRD 2: Release flow (payments, deploy, databases, marketing)

Source: `/Users/petrlavrov/calmmage/obsidian/Inbox/Human-driven AI projects.md`

Raw source excerpt (verbatim):

Release flow
- payments
- Deploy, databases
- Marketing, blog posts, launch flow

Reference: me asking agents to do makefiles and dockerfiles, docker compose
Also asking to guide me step-by-step through release procedure (maybe can do infrastructure as a code instead)

## Goal

Define a reusable release protocol so an AI agent can prepare, verify, and execute release tasks with human checkpoints.

## Scope

In scope:
- Release readiness model.
- Step-by-step release runbook generation.
- Standard Makefile targets and CLI orchestration.
- Docker + compose packaging baseline.
- Database migration safety gates.
- Marketing launch checklist generation.

Out of scope:
- Building a full payment backend from scratch.
- Cloud-specific Terraform implementation in this phase.

## Existing references to reuse

- `/Users/petrlavrov/calmmage/tools/misc/repo_fixer/repo_fixer.py`
- `/Users/petrlavrov/calmmage/tools/misc/repo_fixer/templates/github_publish_workflow.yml.template`
- `/Users/petrlavrov/calmmage/tools/task_management/dev_project_manager/pm_cli.py`
- `/Users/petrlavrov/calmmage/experiments/season_1_winter_2024/dev-docker-compose/docker-compose.yml`

## Release maturity model

States:
- `DRAFT`: release not yet assembled.
- `READY_FOR_DRY_RUN`: gates pass locally/staging.
- `READY_FOR_LAUNCH`: human approved after dry run.
- `LAUNCHED`: deployment + announcement done.
- `ROLLED_BACK`: launch reversed.

## Release spec (single source)

`release/release.yaml`:

```yaml
version: "0.1.0"
service: "human-driven-ai-projects"
release_type: "minor"

gates:
  tests: true
  lint: true
  pyright: true
  migration_dry_run: true
  smoke_test: true

deployment:
  environment: "prod"
  strategy: "rolling"
  compose_file: "deploy/docker-compose.yml"

database:
  migration_command: "uv run alembic upgrade head"
  backup_required: true
  rollback_command: "uv run alembic downgrade -1"

launch:
  changelog: "docs/changelog/0.1.0.md"
  blog_post: "docs/launch/0.1.0.md"
  notify_channels:
    - "telegram"
    - "x"
```

## Standard release steps

1. `prepare`: version bump + changelog draft + release branch.
2. `verify`: tests/lint/type checks/security checks.
3. `package`: build artifacts + docker image + compose config check.
4. `db_preflight`: backup + migration dry-run + integrity check.
5. `deploy_staging`: staging rollout + smoke tests.
6. `human_review`: explicit launch approval gate.
7. `deploy_prod`: production rollout.
8. `post_launch`: announcements, blog post publish, metrics watch.
9. `rollback` (conditional): fast rollback path.

## CLI contract

```python
import typer

app = typer.Typer()

@app.command("plan")
def plan(spec: str = "release/release.yaml"):
    """Generate a concrete release runbook from release spec."""

@app.command("dry-run")
def dry_run(spec: str = "release/release.yaml"):
    """Execute all pre-launch checks without production deployment."""

@app.command("launch")
def launch(spec: str = "release/release.yaml", yes: bool = False):
    """Execute launch with mandatory human confirmation."""

@app.command("rollback")
def rollback(spec: str = "release/release.yaml"):
    """Run rollback sequence and capture incident notes."""
```

## Makefile baseline

```makefile
.PHONY: release-plan release-dry-run release-launch release-rollback

release-plan:
	uv run python -m tools.release.cli plan

release-dry-run:
	uv run python -m tools.release.cli dry-run

release-launch:
	uv run python -m tools.release.cli launch

release-rollback:
	uv run python -m tools.release.cli rollback
```

## Docker + compose baseline

Required files per deployable service:
- `Dockerfile`
- `deploy/docker-compose.yml`

Minimal checks in dry-run:
- `docker build` success.
- `docker compose config` validation.
- App starts and health endpoint returns success.

## DB safety protocol

Mandatory for schema changes:
- Backup snapshot before migration.
- Migration dry run in staging.
- Post-migration smoke query.
- Reversible migration path documented.

DB gate object:

```python
from pydantic import BaseModel

class DatabaseGateResult(BaseModel):
    backup_ok: bool
    dry_run_ok: bool
    smoke_ok: bool
    rollback_tested: bool
```

## Human-in-the-loop checkpoints

Stop points requiring explicit approval:
- After staging smoke tests.
- Before production deployment.
- After launch, before closing release.

Approval message template:
- release version
- key risks
- rollback command
- estimated downtime
- launch channels checklist

## Marketing/launch pack

Generate from release spec:
- Changelog summary
- Launch post skeleton
- “How to try” section
- Known limitations
- CTA links

## Acceptance criteria

- One command creates a full runbook from `release.yaml`.
- Dry-run validates all gates and outputs pass/fail table.
- Launch command refuses execution if any critical gate fails.
- Rollback command executable within one step.
- Launch pack files generated in `docs/launch/`.

## Implementation plan

Phase A:
- `tools/release/cli.py` with `plan`, `dry-run`.
- Parse `release/release.yaml` with Pydantic schema.

Phase B:
- Add deployment adapters (`compose`, optional cloud).
- Add DB gate checks and incident logging.

Phase C:
- Add launch content generators.
- Integrate with daily job runner to schedule release rehearsal.

## Risks and mitigations

- Risk: over-automation of high-risk launch steps.
  - Mitigation: keep explicit human approval gates.
- Risk: environment drift between staging and prod.
  - Mitigation: immutable container builds + same compose baseline.
- Risk: missing rollback confidence.
  - Mitigation: mandatory rollback rehearsal in dry-run for major releases.

## Open questions

- Which payment provider is primary (Stripe/Lemon/etc.)?
- Should release records be stored in repo only or mirrored to Notion?
- Do we require canary deployment by default for web services?
