from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any

from plain.core.models import FlowError

try:
    import yaml
except ImportError:
    yaml = None


class ReleaseState(str, Enum):
    DRAFT = "draft"
    READY_FOR_DRY_RUN = "ready_for_dry_run"
    READY_FOR_LAUNCH = "ready_for_launch"
    LAUNCHED = "launched"
    ROLLED_BACK = "rolled_back"


@dataclass(slots=True)
class ReleaseGates:
    tests: bool = True
    lint: bool = True
    pyright: bool = True
    migration_dry_run: bool = True
    smoke_test: bool = True

    @classmethod
    def from_dict(cls, data: dict[str, Any] | None) -> "ReleaseGates":
        payload = data or {}
        return cls(
            tests=bool(payload.get("tests", True)),
            lint=bool(payload.get("lint", True)),
            pyright=bool(payload.get("pyright", True)),
            migration_dry_run=bool(payload.get("migration_dry_run", True)),
            smoke_test=bool(payload.get("smoke_test", True)),
        )

    def to_dict(self) -> dict[str, bool]:
        return {
            "tests": self.tests,
            "lint": self.lint,
            "pyright": self.pyright,
            "migration_dry_run": self.migration_dry_run,
            "smoke_test": self.smoke_test,
        }


@dataclass(slots=True)
class DeploymentSpec:
    environment: str = "prod"
    strategy: str = "rolling"
    compose_file: str = "deploy/docker-compose.yml"

    @classmethod
    def from_dict(cls, data: dict[str, Any] | None) -> "DeploymentSpec":
        payload = data or {}
        return cls(
            environment=str(payload.get("environment", "prod")),
            strategy=str(payload.get("strategy", "rolling")),
            compose_file=str(payload.get("compose_file", "deploy/docker-compose.yml")),
        )

    def to_dict(self) -> dict[str, str]:
        return {
            "environment": self.environment,
            "strategy": self.strategy,
            "compose_file": self.compose_file,
        }


@dataclass(slots=True)
class DatabaseSpec:
    migration_command: str = "uv run alembic upgrade head"
    backup_required: bool = True
    rollback_command: str = "uv run alembic downgrade -1"

    @classmethod
    def from_dict(cls, data: dict[str, Any] | None) -> "DatabaseSpec":
        payload = data or {}
        return cls(
            migration_command=str(payload.get("migration_command", "uv run alembic upgrade head")),
            backup_required=bool(payload.get("backup_required", True)),
            rollback_command=str(payload.get("rollback_command", "uv run alembic downgrade -1")),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "migration_command": self.migration_command,
            "backup_required": self.backup_required,
            "rollback_command": self.rollback_command,
        }


@dataclass(slots=True)
class LaunchSpec:
    changelog: str = "docs/changelog/0.1.0.md"
    blog_post: str = "docs/launch/0.1.0.md"
    notify_channels: list[str] = field(default_factory=lambda: ["telegram", "x"])

    @classmethod
    def from_dict(cls, data: dict[str, Any] | None) -> "LaunchSpec":
        payload = data or {}
        channels = payload.get("notify_channels", ["telegram", "x"])
        if not isinstance(channels, list):
            channels = [str(channels)]
        return cls(
            changelog=str(payload.get("changelog", "docs/changelog/0.1.0.md")),
            blog_post=str(payload.get("blog_post", "docs/launch/0.1.0.md")),
            notify_channels=[str(item) for item in channels],
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "changelog": self.changelog,
            "blog_post": self.blog_post,
            "notify_channels": self.notify_channels,
        }


@dataclass(slots=True)
class ReleaseSpec:
    version: str
    service: str
    release_type: str
    gates: ReleaseGates = field(default_factory=ReleaseGates)
    deployment: DeploymentSpec = field(default_factory=DeploymentSpec)
    database: DatabaseSpec = field(default_factory=DatabaseSpec)
    launch: LaunchSpec = field(default_factory=LaunchSpec)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "ReleaseSpec":
        version = str(data.get("version", "")).strip()
        service = str(data.get("service", "")).strip()
        release_type = str(data.get("release_type", "")).strip()
        if not version or not service or not release_type:
            raise FlowError("Release spec requires version, service, and release_type")

        return cls(
            version=version,
            service=service,
            release_type=release_type,
            gates=ReleaseGates.from_dict(_as_dict(data.get("gates"))),
            deployment=DeploymentSpec.from_dict(_as_dict(data.get("deployment"))),
            database=DatabaseSpec.from_dict(_as_dict(data.get("database"))),
            launch=LaunchSpec.from_dict(_as_dict(data.get("launch"))),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "version": self.version,
            "service": self.service,
            "release_type": self.release_type,
            "gates": self.gates.to_dict(),
            "deployment": self.deployment.to_dict(),
            "database": self.database.to_dict(),
            "launch": self.launch.to_dict(),
        }


@dataclass(slots=True)
class DatabaseGateResult:
    backup_ok: bool
    dry_run_ok: bool
    smoke_ok: bool
    rollback_tested: bool


@dataclass(slots=True)
class GateCheckResult:
    gate: str
    required: bool
    passed: bool
    details: str
    command: str | None = None
    critical: bool = True


@dataclass(slots=True)
class RunbookStep:
    id: str
    title: str
    description: str
    command: str | None = None
    requires_human_approval: bool = False


@dataclass(slots=True)
class ReleaseRunbook:
    spec: ReleaseSpec
    steps: list[RunbookStep]


@dataclass(slots=True)
class DryRunReport:
    spec: ReleaseSpec
    state: ReleaseState
    checks: list[GateCheckResult]
    db_gate: DatabaseGateResult

    @property
    def all_critical_passed(self) -> bool:
        return all(check.passed or not check.required for check in self.checks if check.critical)


@dataclass(slots=True)
class ReleaseRecord:
    version: str
    state: ReleaseState
    note: str
    updated_at: str


def load_release_spec(spec_path: Path | str) -> ReleaseSpec:
    if yaml is None:
        raise FlowError("PyYAML is required for release flow. Install with: uv add pyyaml")

    path = Path(spec_path)
    if not path.exists():
        raise FlowError(f"Release spec not found: {path}")

    payload = yaml.safe_load(path.read_text()) or {}
    if not isinstance(payload, dict):
        raise FlowError(f"Release spec must be a YAML object: {path}")

    return ReleaseSpec.from_dict(payload)


def dump_release_spec(spec: ReleaseSpec, spec_path: Path | str) -> None:
    if yaml is None:
        raise FlowError("PyYAML is required for release flow. Install with: uv add pyyaml")

    path = Path(spec_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(yaml.safe_dump(spec.to_dict(), sort_keys=False, allow_unicode=False))


def _as_dict(value: Any) -> dict[str, Any]:
    if isinstance(value, dict):
        return value
    return {}
