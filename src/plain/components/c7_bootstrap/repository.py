from __future__ import annotations

import json
from pathlib import Path

from plain.components.c7_bootstrap.models import BootstrapScenario, ScenarioRun
from plain.core.models import FlowError

try:
    import yaml
except ImportError:  # pragma: no cover
    yaml = None


class BootstrapRepository:
    def __init__(
        self,
        scenarios_dir: Path | str = Path("dev/notes/ecosystem/scenarios"),
        runs_dir: Path | str = Path("data/bootstrap_runs"),
    ):
        self.scenarios_dir = Path(scenarios_dir)
        self.runs_dir = Path(runs_dir)

    def ensure_dirs(self) -> None:
        self.scenarios_dir.mkdir(parents=True, exist_ok=True)
        self.runs_dir.mkdir(parents=True, exist_ok=True)

    def load_scenarios(self) -> list[BootstrapScenario]:
        self._require_yaml()
        self.ensure_dirs()
        out: list[BootstrapScenario] = []
        paths = sorted(self.scenarios_dir.glob("*.yaml")) + sorted(
            self.scenarios_dir.glob("*.yml")
        )
        for path in paths:
            try:
                payload = yaml.safe_load(path.read_text()) or {}
            except Exception:
                continue
            if isinstance(payload, dict):
                out.append(BootstrapScenario.from_dict(payload))
        return out

    def save_run(self, run: ScenarioRun) -> Path:
        self.ensure_dirs()
        path = self.runs_dir / f"{run.run_id}.json"
        path.write_text(json.dumps(run.to_dict(), indent=2) + "\n")
        return path

    def load_run(self, run_id: str) -> ScenarioRun:
        self.ensure_dirs()
        path = self.runs_dir / f"{run_id}.json"
        if not path.exists():
            raise FlowError(f"Scenario run not found: {run_id}")
        try:
            payload = json.loads(path.read_text())
        except Exception as exc:
            raise FlowError(f"Invalid scenario run payload: {run_id}") from exc
        if not isinstance(payload, dict):
            raise FlowError(f"Invalid scenario run payload: {run_id}")
        return ScenarioRun.from_dict(payload)

    def list_runs(self) -> list[ScenarioRun]:
        self.ensure_dirs()
        runs: list[ScenarioRun] = []
        for path in sorted(self.runs_dir.glob("*.json")):
            try:
                payload = json.loads(path.read_text())
            except Exception:
                continue
            if isinstance(payload, dict):
                runs.append(ScenarioRun.from_dict(payload))
        return sorted(runs, key=lambda run: run.started_at, reverse=True)

    @staticmethod
    def _require_yaml() -> None:
        if yaml is None:  # pragma: no cover
            raise FlowError("PyYAML is required for scenario registry. Install with: uv add pyyaml")
