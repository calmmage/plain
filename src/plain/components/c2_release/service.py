from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from plain.components.c2_release.models import (
    DatabaseGateResult,
    DryRunReport,
    GateCheckResult,
    ReleaseRecord,
    ReleaseRunbook,
    ReleaseSpec,
    ReleaseState,
    RunbookStep,
    load_release_spec,
)
from plain.core.models import FlowError


DEFAULT_SPEC = Path("release/release.yaml")
DEFAULT_STATE_FILE = Path("release/state.json")
DEFAULT_RUNBOOK_DIR = Path("release/runbooks")
DEFAULT_INCIDENT_DIR = Path("release/incidents")


@dataclass(slots=True)
class ReleaseService:
    workspace: Path = Path(".")

    def plan(self, spec_path: str | Path = DEFAULT_SPEC) -> tuple[ReleaseRunbook, Path]:
        spec = load_release_spec(self._resolve(spec_path))

        steps = [
            RunbookStep(
                id="prepare",
                title="Prepare release",
                description="Create release branch, confirm version, and draft changelog.",
                command=f"git checkout -b release/{spec.version}",
            ),
            RunbookStep(
                id="verify",
                title="Verify quality gates",
                description="Run test, lint, and type checks before packaging.",
                command="make test",
            ),
            RunbookStep(
                id="package",
                title="Package deployment artifacts",
                description="Build docker image and validate compose configuration.",
                command="make release-dry-run",
            ),
            RunbookStep(
                id="db_preflight",
                title="Database preflight",
                description="Confirm backup requirement and migration dry-run path.",
                command=spec.database.migration_command,
            ),
            RunbookStep(
                id="deploy_staging",
                title="Deploy staging",
                description="Roll out to staging and run smoke checks.",
                command=f"docker compose -f {spec.deployment.compose_file} up -d",
            ),
            RunbookStep(
                id="human_review",
                title="Human review checkpoint",
                description="Human confirms risks and approves production launch.",
                requires_human_approval=True,
            ),
            RunbookStep(
                id="deploy_prod",
                title="Deploy production",
                description="Deploy to production with configured strategy.",
                command=f"deploy --env {spec.deployment.environment} --strategy {spec.deployment.strategy}",
                requires_human_approval=True,
            ),
            RunbookStep(
                id="post_launch",
                title="Post-launch checklist",
                description="Publish changelog/blog and monitor key metrics.",
                command="make release-launch",
                requires_human_approval=True,
            ),
            RunbookStep(
                id="rollback",
                title="Rollback path",
                description="Execute rollback command and capture incident notes if needed.",
                command=spec.database.rollback_command,
            ),
        ]

        runbook = ReleaseRunbook(spec=spec, steps=steps)
        output = self.write_runbook(runbook)
        self._save_state(spec, ReleaseState.DRAFT, "Release runbook generated")
        return runbook, output

    def dry_run(self, spec_path: str | Path = DEFAULT_SPEC) -> DryRunReport:
        spec = load_release_spec(self._resolve(spec_path))

        pyproject = self._resolve("pyproject.toml")
        ruff = self._resolve("ruff.toml")
        tests_dir = self._resolve("tests")
        dockerfile = self._resolve("Dockerfile")
        compose = self._resolve(spec.deployment.compose_file)
        backup_plan = self._resolve("release/backup-plan.md")

        checks = [
            GateCheckResult(
                gate="tests",
                required=spec.gates.tests,
                passed=(not spec.gates.tests) or (tests_dir.exists() and pyproject.exists()),
                details=(
                    "tests directory and pyproject found"
                    if tests_dir.exists() and pyproject.exists()
                    else "missing tests directory or pyproject.toml"
                ),
                command="uv run pytest src tests",
            ),
            GateCheckResult(
                gate="lint",
                required=spec.gates.lint,
                passed=(not spec.gates.lint) or ruff.exists() or self._file_contains(pyproject, "ruff"),
                details=(
                    "ruff configuration found"
                    if ruff.exists() or self._file_contains(pyproject, "ruff")
                    else "ruff configuration missing"
                ),
                command="uv run ruff check .",
            ),
            GateCheckResult(
                gate="pyright",
                required=spec.gates.pyright,
                passed=(not spec.gates.pyright)
                or self._file_contains(pyproject, "pyright"),
                details=(
                    "pyright configured in project dependencies"
                    if self._file_contains(pyproject, "pyright")
                    else "pyright dependency or config missing"
                ),
                command="uv run pyright",
            ),
            GateCheckResult(
                gate="migration_dry_run",
                required=spec.gates.migration_dry_run,
                passed=(not spec.gates.migration_dry_run)
                or bool(spec.database.migration_command and spec.database.rollback_command),
                details=(
                    "migration and rollback commands are configured"
                    if spec.database.migration_command and spec.database.rollback_command
                    else "migration or rollback command missing"
                ),
                command=spec.database.migration_command,
            ),
            GateCheckResult(
                gate="smoke_test",
                required=spec.gates.smoke_test,
                passed=(not spec.gates.smoke_test)
                or (dockerfile.exists() and compose.exists() and self._file_contains(compose, "services:")),
                details=(
                    "Dockerfile and compose services are present"
                    if dockerfile.exists() and compose.exists() and self._file_contains(compose, "services:")
                    else "Dockerfile/compose baseline incomplete"
                ),
                command=f"docker compose -f {spec.deployment.compose_file} config",
            ),
        ]

        db_gate = DatabaseGateResult(
            backup_ok=(not spec.database.backup_required) or backup_plan.exists(),
            dry_run_ok=bool(spec.database.migration_command),
            smoke_ok=compose.exists(),
            rollback_tested=bool(spec.database.rollback_command),
        )

        all_required_passed = all(check.passed for check in checks if check.required)
        state = ReleaseState.READY_FOR_DRY_RUN if all_required_passed else ReleaseState.DRAFT
        self._save_state(spec, state, "Dry-run checks evaluated")

        return DryRunReport(spec=spec, state=state, checks=checks, db_gate=db_gate)

    def launch(
        self,
        spec_path: str | Path = DEFAULT_SPEC,
        yes: bool = False,
    ) -> tuple[DryRunReport, list[Path]]:
        report = self.dry_run(spec_path)

        if not report.all_critical_passed:
            failures = [check.gate for check in report.checks if check.required and not check.passed]
            raise FlowError(
                "Launch blocked. Critical gates failed: " + ", ".join(sorted(failures))
            )

        spec = report.spec
        self._save_state(spec, ReleaseState.READY_FOR_LAUNCH, "Dry-run passed, waiting for human approval")

        if not yes:
            raise FlowError(
                "Launch requires explicit human approval. Re-run with --yes after review.\n\n"
                + self.approval_message(spec, report)
            )

        generated = self.generate_launch_pack(spec)
        self._save_state(spec, ReleaseState.LAUNCHED, "Launch flow executed")
        return report, generated

    def rollback(self, spec_path: str | Path = DEFAULT_SPEC) -> Path:
        spec = load_release_spec(self._resolve(spec_path))
        now = self._now_iso().replace(":", "-")
        incident_dir = self._resolve(DEFAULT_INCIDENT_DIR)
        incident_dir.mkdir(parents=True, exist_ok=True)
        incident_path = incident_dir / f"{spec.version}-rollback-{now}.md"

        incident_path.write_text(
            "\n".join(
                [
                    f"# Rollback Incident - {spec.service} {spec.version}",
                    "",
                    f"- timestamp: {self._now_iso()}",
                    f"- environment: {spec.deployment.environment}",
                    f"- rollback_command: {spec.database.rollback_command}",
                    "",
                    "## Notes",
                    "- describe trigger and blast radius",
                    "- capture customer impact",
                    "- list immediate follow-up actions",
                ]
            )
            + "\n"
        )

        self._save_state(spec, ReleaseState.ROLLED_BACK, f"Rollback captured: {incident_path}")
        return incident_path

    def approval_message(self, spec: ReleaseSpec, report: DryRunReport) -> str:
        failing = [check.gate for check in report.checks if check.required and not check.passed]
        risk_line = "none" if not failing else ", ".join(failing)
        channels = ", ".join(spec.launch.notify_channels)
        return "\n".join(
            [
                f"release version: {spec.version}",
                f"key risks: {risk_line}",
                f"rollback command: {spec.database.rollback_command}",
                "estimated downtime: TBD",
                f"launch channels: {channels}",
            ]
        )

    def generate_launch_pack(self, spec: ReleaseSpec) -> list[Path]:
        changelog = self._resolve(spec.launch.changelog)
        blog_post = self._resolve(spec.launch.blog_post)
        changelog.parent.mkdir(parents=True, exist_ok=True)
        blog_post.parent.mkdir(parents=True, exist_ok=True)

        if not changelog.exists():
            changelog.write_text(
                "\n".join(
                    [
                        f"# Changelog {spec.version}",
                        "",
                        "## Summary",
                        "- describe product changes",
                        "",
                        "## How to try",
                        "- add command or URL",
                        "",
                        "## Known limitations",
                        "- list current constraints",
                    ]
                )
                + "\n"
            )

        if not blog_post.exists():
            blog_post.write_text(
                "\n".join(
                    [
                        f"# Launch Post {spec.service} {spec.version}",
                        "",
                        "## What shipped",
                        "- summarize the release",
                        "",
                        "## How to try",
                        "- usage instructions",
                        "",
                        "## CTA",
                        "- add links and channels",
                    ]
                )
                + "\n"
            )

        return [changelog, blog_post]

    def write_runbook(self, runbook: ReleaseRunbook) -> Path:
        runbook_dir = self._resolve(DEFAULT_RUNBOOK_DIR)
        runbook_dir.mkdir(parents=True, exist_ok=True)
        output = runbook_dir / f"{runbook.spec.version}.md"

        lines: list[str] = [
            f"# Release Runbook {runbook.spec.version}",
            "",
            f"- service: {runbook.spec.service}",
            f"- release_type: {runbook.spec.release_type}",
            f"- environment: {runbook.spec.deployment.environment}",
            "",
            "## Steps",
            "",
        ]

        for idx, step in enumerate(runbook.steps, start=1):
            lines.append(f"{idx}. {step.title} (`{step.id}`)")
            lines.append(f"   - {step.description}")
            if step.command:
                lines.append(f"   - command: `{step.command}`")
            if step.requires_human_approval:
                lines.append("   - requires human approval")

        output.write_text("\n".join(lines) + "\n")
        return output

    def read_state_records(self) -> list[ReleaseRecord]:
        path = self._resolve(DEFAULT_STATE_FILE)
        if not path.exists():
            return []

        data = json.loads(path.read_text() or "[]")
        if not isinstance(data, list):
            return []

        records: list[ReleaseRecord] = []
        for item in data:
            if not isinstance(item, dict):
                continue
            version = str(item.get("version", "")).strip()
            state_value = str(item.get("state", ReleaseState.DRAFT.value)).strip()
            note = str(item.get("note", ""))
            updated_at = str(item.get("updated_at", ""))
            if not version:
                continue
            try:
                state = ReleaseState(state_value)
            except ValueError:
                state = ReleaseState.DRAFT
            records.append(
                ReleaseRecord(
                    version=version,
                    state=state,
                    note=note,
                    updated_at=updated_at,
                )
            )
        return records

    def _save_state(self, spec: ReleaseSpec, state: ReleaseState, note: str) -> None:
        path = self._resolve(DEFAULT_STATE_FILE)
        path.parent.mkdir(parents=True, exist_ok=True)

        records = self.read_state_records()
        now = self._now_iso()

        filtered = [record for record in records if record.version != spec.version]
        filtered.append(
            ReleaseRecord(
                version=spec.version,
                state=state,
                note=note,
                updated_at=now,
            )
        )

        payload = [
            {
                "version": record.version,
                "state": record.state.value,
                "note": record.note,
                "updated_at": record.updated_at,
            }
            for record in filtered
        ]
        path.write_text(json.dumps(payload, indent=2) + "\n")

    def _resolve(self, path: str | Path) -> Path:
        resolved = Path(path)
        if resolved.is_absolute():
            return resolved
        return self.workspace / resolved

    @staticmethod
    def _file_contains(path: Path, text: str) -> bool:
        if not path.exists():
            return False
        try:
            return text in path.read_text()
        except Exception:
            return False

    @staticmethod
    def _now_iso() -> str:
        return datetime.now(timezone.utc).replace(microsecond=0).isoformat()
