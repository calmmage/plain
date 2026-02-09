from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

from plain.components.c1_flow.repository import FlowRepository
from plain.components.c1_flow.service import FlowService
from plain.components.c2_release.models import DryRunReport
from plain.components.c2_release.service import ReleaseService
from plain.components.c3_principles.models import PrincipleNote
from plain.components.c3_principles.service import PrinciplesService
from plain.components.c4_daily_runner.models import DailyJobResult, RepoState
from plain.components.c4_daily_runner.service import DailyImplementerService
from plain.components.c5_ingest.models import ObsidianIngestResult
from plain.components.c5_ingest.repository import ObsidianIngestRepository
from plain.components.c5_ingest.service import ObsidianIngestService
from plain.components.c6_review.models import ReviewIngestResult, ReviewItem
from plain.components.c6_review.repository import ReviewRepository
from plain.components.c6_review.service import ReviewService
from plain.components.c7_bootstrap.models import ExecutionMode, ScenarioRun
from plain.components.c7_bootstrap.repository import BootstrapRepository
from plain.components.c7_bootstrap.service import BootstrapService
from plain.components.c8_orchestrator.models import ModuleStatus, WorkflowStatusSnapshot, utc_now
from plain.core.models import FlowError


@dataclass(slots=True)
class OrchestratorService:
    flow_service: FlowService
    flow_repository: FlowRepository
    release_service: ReleaseService
    principles_service: PrinciplesService
    daily_service: DailyImplementerService
    obsidian_service: ObsidianIngestService
    obsidian_repository: ObsidianIngestRepository
    review_service: ReviewService
    review_repository: ReviewRepository
    bootstrap_service: BootstrapService
    bootstrap_repository: BootstrapRepository
    workspace: Path = Path(".")
    daily_log_dir: Path = Path("dev/notes/ecosystem/daily_runs")

    @classmethod
    def create_default(cls) -> "OrchestratorService":
        flow_service = FlowService.create_default()
        principles_service = PrinciplesService.create_default()
        obsidian_service = ObsidianIngestService.create_default()
        review_service = ReviewService.create_default()
        bootstrap_service = BootstrapService.create_default()
        return cls(
            flow_service=flow_service,
            flow_repository=flow_service.repository,
            release_service=ReleaseService(),
            principles_service=principles_service,
            daily_service=DailyImplementerService(),
            obsidian_service=obsidian_service,
            obsidian_repository=obsidian_service.repository,
            review_service=review_service,
            review_repository=review_service.repository,
            bootstrap_service=bootstrap_service,
            bootstrap_repository=bootstrap_service.repository,
        )

    # Unified command wrappers
    def run_ingest(
        self,
        note_roots: Iterable[str | Path] | None = None,
        force_full_scan: bool = False,
    ) -> ObsidianIngestResult:
        return self.obsidian_service.run_ingest(
            note_roots=note_roots,
            force_full_scan=force_full_scan,
        )

    def run_daily(
        self,
        task_sources: Iterable[str | Path] | None = None,
        context_sources: Iterable[str | Path] | None = None,
        repo_path: str = ".",
        repo_clean: bool = False,
        client: str = "codex",
        force: bool = False,
    ) -> DailyJobResult:
        return self.daily_service.run_daily_feature_implementer(
            task_sources=task_sources or [
                "dev/notes/ecosystem/tasks.md",
                "dev/notes/tasks.md",
            ],
            context_sources=context_sources or [
                "dev/notes",
                "README.md",
                "release/release.yaml",
            ],
            repo_state=RepoState(is_clean=repo_clean, root_path=repo_path),
            client=client,
            force=force,
            tests_passed=True,
        )

    def review_queue(self, status: str | None = None, ready_only: bool = False) -> list[ReviewItem]:
        return self.review_service.list_items(status=status, ready_only=ready_only)

    def ingest_review_packets(
        self,
        packet_paths: Iterable[str | Path] | None = None,
        project_id: str | None = None,
        feature_id: str | None = None,
        original_vision: str | None = None,
    ) -> ReviewIngestResult:
        return self.review_service.ingest_packets(
            packet_sources=packet_paths,
            project_id=project_id,
            feature_id=feature_id,
            original_vision=original_vision,
        )

    def phase_board(self, project: str) -> list[dict[str, str]]:
        return self.flow_service.board_rows(project)

    def release_dry_run(self, spec_path: str = "release/release.yaml") -> DryRunReport:
        return self.release_service.dry_run(spec_path=spec_path)

    def principles_capture(
        self,
        title: str,
        raw: str,
        source: str,
        normalized_rule: str | None = None,
        rationale: str | None = None,
        tag: Iterable[str] | None = None,
        source_session_id: str | None = None,
    ) -> PrincipleNote:
        return self.principles_service.capture(
            title=title,
            raw_quote=raw,
            source_path=source,
            normalized_rule=normalized_rule,
            rationale=rationale,
            tags=list(tag or []),
            source_session_id=source_session_id,
        )

    def bootstrap_run(
        self,
        scenario_id: str,
        mode: str = ExecutionMode.INTERACTIVE.value,
        max_steps: int = 40,
        max_wall_time_sec: int = 1800,
        allow_destructive: bool = False,
    ) -> ScenarioRun:
        return self.bootstrap_service.run_scenario(
            scenario_id=scenario_id,
            mode=mode,
            max_steps=max_steps,
            max_wall_time_sec=max_wall_time_sec,
            allow_destructive=allow_destructive,
        )

    def bootstrap_resume(
        self,
        run_id: str,
        mode: str | None = None,
        max_steps: int = 40,
        max_wall_time_sec: int = 1800,
        allow_destructive: bool = False,
    ) -> ScenarioRun:
        return self.bootstrap_service.resume_run(
            run_id=run_id,
            mode=mode,
            max_steps=max_steps,
            max_wall_time_sec=max_wall_time_sec,
            allow_destructive=allow_destructive,
        )

    # Global status snapshot
    def workflow_status(self, project: str | None = None) -> WorkflowStatusSnapshot:
        modules = [
            self._m1_status(project),
            self._m2_status(),
            self._m3_status(),
            self._m4_status(),
            self._m5_status(),
            self._m6_status(),
            self._m7_status(),
            self._m8_status(),
        ]
        return WorkflowStatusSnapshot(generated_at=utc_now(), modules=modules)

    def _m1_status(self, project: str | None = None) -> ModuleStatus:
        slugs = self.flow_repository.list_project_slugs()
        projects = []
        for slug in slugs:
            try:
                item = self.flow_repository.load(slug)
            except FlowError:
                continue
            if project and project not in {slug, item.project_id, item.project_name}:
                continue
            projects.append(item)

        phase_counts = {"make_it_work": 0, "test": 0, "polish": 0}
        feature_count = 0
        for item in projects:
            feature_count += len(item.features)
            for feature in item.features:
                phase_counts[feature.current_phase.value] = (
                    phase_counts.get(feature.current_phase.value, 0) + 1
                )

        status = "healthy" if projects else "idle"
        details = {
            "projects": len(projects),
            "features": feature_count,
            "phase_counts": phase_counts,
        }
        if project:
            details["project_filter"] = project
        return ModuleStatus(module_id="m1", title="Three-phase flow", status=status, details=details)

    def _m2_status(self) -> ModuleStatus:
        spec_path = self._resolve("release/release.yaml")
        if not spec_path.exists():
            return ModuleStatus(
                module_id="m2",
                title="Release flow",
                status="missing",
                details={"spec": str(spec_path), "error": "release spec missing"},
            )

        try:
            report = self.release_service.dry_run(spec_path=spec_path)
            failed = [row.gate for row in report.checks if row.required and not row.passed]
            status = "ready" if report.all_critical_passed else "attention"
            details = {
                "spec": str(spec_path),
                "state": report.state.value,
                "required_failed": failed,
            }
            return ModuleStatus("m2", "Release flow", status, details)
        except FlowError as exc:
            return ModuleStatus(
                "m2",
                "Release flow",
                "error",
                {"spec": str(spec_path), "error": str(exc)},
            )

    def _m3_status(self) -> ModuleStatus:
        principles = self.principles_service.list_principles(status="all")
        candidates = self.principles_service.list_candidates(status="all")
        approved_principles = len([item for item in principles if item.status.value == "approved"])
        approved_candidates = len([item for item in candidates if item.status.value == "approved"])
        status = "healthy" if principles else "idle"
        return ModuleStatus(
            "m3",
            "Principles->skills",
            status,
            {
                "principles": len(principles),
                "approved_principles": approved_principles,
                "candidates": len(candidates),
                "approved_candidates": approved_candidates,
            },
        )

    def _m4_status(self) -> ModuleStatus:
        log_dir = self._resolve(self.daily_log_dir)
        if not log_dir.exists():
            return ModuleStatus(
                "m4",
                "Daily implementer",
                "idle",
                {"runs": 0, "latest_run": None},
            )

        runs = sorted(log_dir.glob("*.json"))
        latest = runs[-1].name if runs else None
        status = "healthy" if runs else "idle"
        return ModuleStatus(
            "m4",
            "Daily implementer",
            status,
            {"runs": len(runs), "latest_run": latest},
        )

    def _m5_status(self) -> ModuleStatus:
        items = self.obsidian_repository.load_items()
        queue = self.obsidian_repository.load_review_queue()
        duplicates = self.obsidian_repository.load_duplicates()
        status = "healthy" if items else "idle"
        return ModuleStatus(
            "m5",
            "Obsidian ingest",
            status,
            {
                "items": len(items),
                "pending_review": len(queue),
                "duplicate_candidates": len(duplicates),
            },
        )

    def _m6_status(self) -> ModuleStatus:
        items = self.review_repository.load_items()
        counts: dict[str, int] = {}
        for item in items:
            key = item.status.value
            counts[key] = counts.get(key, 0) + 1
        status = "idle"
        if items:
            status = "attention" if counts.get("changes_requested", 0) else "healthy"
        return ModuleStatus(
            "m6",
            "Review queue",
            status,
            {
                "items": len(items),
                "status_counts": counts,
            },
        )

    def _m7_status(self) -> ModuleStatus:
        scenarios = self.bootstrap_service.list_scenarios()
        runs = self.bootstrap_repository.list_runs()
        paused = len([run for run in runs if run.status.value == "paused"])
        status = "healthy" if len(scenarios) >= 6 else "attention"
        return ModuleStatus(
            "m7",
            "Bootstrap scenarios",
            status,
            {
                "scenarios": len(scenarios),
                "runs": len(runs),
                "paused_runs": paused,
            },
        )

    def _m8_status(self) -> ModuleStatus:
        ecosystem = self._resolve("dev/notes/ecosystem")
        demos = self._resolve("dev/notes/demos")
        status = "healthy" if ecosystem.exists() and demos.exists() else "attention"
        return ModuleStatus(
            "m8",
            "Coordination layer",
            status,
            {
                "ecosystem_dir": str(ecosystem),
                "ecosystem_exists": ecosystem.exists(),
                "demos_dir": str(demos),
                "demos_exists": demos.exists(),
            },
        )

    def _resolve(self, path: str | Path) -> Path:
        candidate = Path(path)
        if candidate.is_absolute():
            return candidate
        return self.workspace / candidate
