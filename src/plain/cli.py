from __future__ import annotations

import argparse
import sys
from typing import Sequence

from plain.components.c1_flow.service import FlowService
from plain.components.c2_release.render import render_dry_run_report, render_launch_pack, render_runbook
from plain.components.c2_release.service import ReleaseService
from plain.components.c3_principles.models import SkillTargetScope
from plain.components.c3_principles.service import PrinciplesService
from plain.components.c4_daily_runner.models import RepoState, WorkspaceType
from plain.components.c4_daily_runner.render import render_daily_result
from plain.components.c4_daily_runner.service import DailyImplementerService
from plain.core.models import FlowError, Phase


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="flow", description="Three-phase flow CLI")
    subparsers = parser.add_subparsers(dest="command", required=True)

    init_parser = subparsers.add_parser("init", help="Initialize a project flow")
    init_parser.add_argument("project_name")
    init_parser.add_argument("--repo", required=True)
    init_parser.add_argument("--tags", nargs="*", default=[])

    feature_parser = subparsers.add_parser("feature", help="Feature flow operations")
    feature_sub = feature_parser.add_subparsers(dest="feature_command", required=True)

    feature_add = feature_sub.add_parser("add", help="Add a feature to a project")
    feature_add.add_argument("project")
    feature_add.add_argument("title")
    feature_add.add_argument("--vision", required=True)
    feature_add.add_argument("--feature-id")

    feature_show = feature_sub.add_parser("show", help="Show feature details")
    feature_show.add_argument("project")
    feature_show.add_argument("feature_id")

    phase_parser = subparsers.add_parser("phase", help="Phase operations")
    phase_sub = phase_parser.add_subparsers(dest="phase_command", required=True)

    phase_start = phase_sub.add_parser("start", help="Start a phase")
    phase_start.add_argument("project")
    phase_start.add_argument("feature_id")
    phase_start.add_argument("phase", choices=[item.value for item in Phase])

    phase_advance = phase_sub.add_parser("advance", help="Advance current phase")
    phase_advance.add_argument("project")
    phase_advance.add_argument("feature_id")

    feedback_parser = subparsers.add_parser("feedback", help="Feedback operations")
    feedback_sub = feedback_parser.add_subparsers(dest="feedback_command", required=True)

    feedback_add = feedback_sub.add_parser("add", help="Add feedback to current phase")
    feedback_add.add_argument("project")
    feedback_add.add_argument("feature_id")
    feedback_add.add_argument("--text", required=True)

    conv_parser = subparsers.add_parser("conv", help="Conversation operations")
    conv_sub = conv_parser.add_subparsers(dest="conv_command", required=True)

    conv_link = conv_sub.add_parser("link", help="Link conversation to phase")
    conv_link.add_argument("project")
    conv_link.add_argument("feature_id")
    conv_link.add_argument("--client", required=True)
    conv_link.add_argument("--session-id", required=True)
    conv_link.add_argument("--cwd", required=True)
    conv_link.add_argument("--summary")
    conv_link.add_argument("--phase", choices=[item.value for item in Phase])

    conv_resume = conv_sub.add_parser("resume", help="Print resume command")
    conv_resume.add_argument("project")
    conv_resume.add_argument("feature_id")
    conv_resume.add_argument("--phase", choices=[item.value for item in Phase])

    artifact_parser = subparsers.add_parser("artifact", help="Artifact operations")
    artifact_sub = artifact_parser.add_subparsers(dest="artifact_command", required=True)

    artifact_add = artifact_sub.add_parser("add", help="Add artifact to phase")
    artifact_add.add_argument("project")
    artifact_add.add_argument("feature_id")
    artifact_add.add_argument("--kind", required=True)
    artifact_add.add_argument("--path", required=True)
    artifact_add.add_argument("--note")
    artifact_add.add_argument("--phase", choices=[item.value for item in Phase])

    meta_parser = subparsers.add_parser("meta", help="Structured phase metadata")
    meta_sub = meta_parser.add_subparsers(dest="meta_command", required=True)

    meta_add = meta_sub.add_parser("add", help="Add phase metadata")
    meta_add.add_argument("project")
    meta_add.add_argument("feature_id")
    meta_add.add_argument("--code-link")
    meta_add.add_argument("--entry-point")
    meta_add.add_argument("--explanation")
    meta_add.add_argument("--phase", choices=[item.value for item in Phase])

    board_parser = subparsers.add_parser("board", help="Show board view")
    board_parser.add_argument("project")

    snapshot_parser = subparsers.add_parser("snapshot", help="Show concise status snapshot")
    snapshot_parser.add_argument("project")

    release_parser = subparsers.add_parser("release", help="Release flow orchestration")
    release_sub = release_parser.add_subparsers(dest="release_command", required=True)

    release_plan = release_sub.add_parser("plan", help="Generate release runbook")
    release_plan.add_argument("--spec", default="release/release.yaml")

    release_dry_run = release_sub.add_parser("dry-run", help="Run release dry-run checks")
    release_dry_run.add_argument("--spec", default="release/release.yaml")

    release_launch = release_sub.add_parser("launch", help="Launch after passing gates")
    release_launch.add_argument("--spec", default="release/release.yaml")
    release_launch.add_argument("--yes", action="store_true")

    release_rollback = release_sub.add_parser("rollback", help="Run rollback flow")
    release_rollback.add_argument("--spec", default="release/release.yaml")

    principle_parser = subparsers.add_parser(
        "principle", help="Capture and promote principles into reusable skills"
    )
    principle_sub = principle_parser.add_subparsers(
        dest="principle_command", required=True
    )

    principle_capture = principle_sub.add_parser(
        "capture", help="Capture a principle note"
    )
    principle_capture.add_argument("--title", required=True)
    principle_capture.add_argument("--raw", required=True)
    principle_capture.add_argument("--source", required=True)
    principle_capture.add_argument("--normalized-rule")
    principle_capture.add_argument("--rationale")
    principle_capture.add_argument("--example-good")
    principle_capture.add_argument("--example-bad")
    principle_capture.add_argument("--tag", action="append", default=[])
    principle_capture.add_argument("--source-session-id")

    principle_list = principle_sub.add_parser("list", help="List captured principles")
    principle_list.add_argument(
        "--status", default="all", choices=["all", "draft", "approved"]
    )

    principle_list_candidates = principle_sub.add_parser(
        "list-candidates", help="List skill candidates"
    )
    principle_list_candidates.add_argument(
        "--status", default="all", choices=["all", "draft", "review", "approved", "rejected"]
    )

    principle_promote = principle_sub.add_parser(
        "promote", help="Promote principle(s) into skill candidate"
    )
    principle_promote.add_argument("principle_id")
    principle_promote.add_argument("--skill-name", required=True)
    principle_promote.add_argument(
        "--scope", default=SkillTargetScope.CODING.value, choices=[item.value for item in SkillTargetScope]
    )
    principle_promote.add_argument(
        "--include-principle-id", action="append", default=[]
    )

    principle_test = principle_sub.add_parser(
        "test-skill", help="Run rubric check for generated skill candidate"
    )
    principle_test.add_argument("candidate_id")
    principle_test.add_argument("--prompt", required=True)

    principle_approve = principle_sub.add_parser(
        "approve-skill", help="Approve reviewed skill candidate"
    )
    principle_approve.add_argument("candidate_id")

    principle_deploy = principle_sub.add_parser(
        "deploy", help="Deploy approved principle bundle into instruction files"
    )
    principle_deploy.add_argument("--target", action="append", default=None)

    daily_parser = subparsers.add_parser(
        "daily", help="Run daily feature implementer selection and packet generation"
    )
    daily_sub = daily_parser.add_subparsers(dest="daily_command", required=True)

    daily_score = daily_sub.add_parser("score", help="Score candidate tasks")
    daily_score.add_argument("--task-source", action="append", default=[])
    daily_score.add_argument("--daily-budget", type=int, default=180)

    daily_run = daily_sub.add_parser("run", help="Run daily_feature_implementer job")
    daily_run.add_argument("--task-source", action="append", default=[])
    daily_run.add_argument("--context-source", action="append", default=[])
    daily_run.add_argument("--client", default="codex")
    daily_run.add_argument("--repo-path", default=".")
    daily_run.add_argument("--repo-clean", action="store_true")
    daily_run.add_argument("--task-risk", choices=["low", "medium", "high"])
    daily_run.add_argument("--daily-budget", type=int, default=180)
    daily_run.add_argument("--max-file-changes", type=int, default=40)
    daily_run.add_argument("--changed-file", action="append", default=[])
    daily_run.add_argument("--tests-passed", action="store_true")
    daily_run.add_argument("--force", action="store_true")
    daily_run.add_argument(
        "--workspace",
        choices=[item.value for item in WorkspaceType],
        help="Optional workspace override",
    )

    return parser


def run_cli(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    service = FlowService.create_default()
    release_service = ReleaseService()
    principles_service = PrinciplesService.create_default()
    daily_service = DailyImplementerService()

    try:
        if args.command == "init":
            project = service.init_project(
                project_name=args.project_name,
                repository_path=args.repo,
                tags=args.tags,
            )
            print(f"Initialized project flow: {project.project_name}")
            print(f"project_id={project.project_id}")
            return 0

        if args.command == "feature" and args.feature_command == "add":
            feature = service.add_feature(
                project_identifier=args.project,
                title=args.title,
                vision=args.vision,
                feature_id=args.feature_id,
            )
            print(f"Added feature {feature.feature_id} ({feature.title})")
            return 0

        if args.command == "feature" and args.feature_command == "show":
            feature = service.get_feature(args.project, args.feature_id)
            print(_format_feature(feature))
            return 0

        if args.command == "phase" and args.phase_command == "start":
            feature = service.phase_start(args.project, args.feature_id, args.phase)
            print(f"Feature {feature.feature_id} phase started: {feature.current_phase.value}")
            return 0

        if args.command == "phase" and args.phase_command == "advance":
            feature = service.phase_advance(args.project, args.feature_id)
            print(f"Feature {feature.feature_id} advanced to: {feature.current_phase.value}")
            return 0

        if args.command == "feedback" and args.feedback_command == "add":
            feature = service.add_feedback(args.project, args.feature_id, args.text)
            print(f"Feedback added for {feature.feature_id} ({feature.current_phase.value})")
            return 0

        if args.command == "conv" and args.conv_command == "link":
            conv = service.link_conversation(
                project_identifier=args.project,
                feature_id=args.feature_id,
                client=args.client,
                session_id=args.session_id,
                cwd=args.cwd,
                summary=args.summary,
                phase=args.phase,
            )
            print(f"Conversation linked: {conv.client}:{conv.session_id}")
            return 0

        if args.command == "conv" and args.conv_command == "resume":
            print(service.resume_command(args.project, args.feature_id, phase=args.phase))
            return 0

        if args.command == "artifact" and args.artifact_command == "add":
            artifact = service.add_artifact(
                project_identifier=args.project,
                feature_id=args.feature_id,
                kind=args.kind,
                path=args.path,
                note=args.note,
                phase=args.phase,
            )
            print(f"Artifact added: {artifact.kind} -> {artifact.path}")
            return 0

        if args.command == "meta" and args.meta_command == "add":
            feature = service.add_phase_metadata(
                project_identifier=args.project,
                feature_id=args.feature_id,
                code_link=args.code_link,
                entry_point=args.entry_point,
                explanation=args.explanation,
                phase=args.phase,
            )
            print(f"Phase metadata updated for {feature.feature_id}")
            return 0

        if args.command == "board":
            rows = service.board_rows(args.project)
            print(render_table(rows))
            return 0

        if args.command == "snapshot":
            print(service.snapshot(args.project))
            return 0

        if args.command == "release" and args.release_command == "plan":
            runbook, output = release_service.plan(spec_path=args.spec)
            print(render_runbook(runbook))
            print(f"\nrunbook_file={output}")
            return 0

        if args.command == "release" and args.release_command == "dry-run":
            report = release_service.dry_run(spec_path=args.spec)
            print(render_dry_run_report(report))
            return 0

        if args.command == "release" and args.release_command == "launch":
            report, launch_paths = release_service.launch(spec_path=args.spec, yes=args.yes)
            print(render_dry_run_report(report))
            print("")
            print(render_launch_pack([str(path) for path in launch_paths]))
            return 0

        if args.command == "release" and args.release_command == "rollback":
            incident = release_service.rollback(spec_path=args.spec)
            print(f"rollback_recorded={incident}")
            return 0

        if args.command == "principle" and args.principle_command == "capture":
            note = principles_service.capture(
                title=args.title,
                raw_quote=args.raw,
                source_path=args.source,
                normalized_rule=args.normalized_rule,
                rationale=args.rationale,
                example_good=args.example_good,
                example_bad=args.example_bad,
                tags=args.tag,
                source_session_id=args.source_session_id,
            )
            print(f"captured_principle={note.principle_id}")
            return 0

        if args.command == "principle" and args.principle_command == "list":
            notes = principles_service.list_principles(status=args.status)
            print(_format_principles(notes))
            return 0

        if args.command == "principle" and args.principle_command == "list-candidates":
            candidates = principles_service.list_candidates(status=args.status)
            print(_format_candidates(candidates))
            return 0

        if args.command == "principle" and args.principle_command == "promote":
            candidate = principles_service.promote(
                principle_id=args.principle_id,
                skill_name=args.skill_name,
                target_scope=args.scope,
                include_principle_ids=args.include_principle_id,
            )
            print(f"candidate_id={candidate.candidate_id}")
            if candidate.skill_path:
                print(f"skill_path={candidate.skill_path}")
            return 0

        if args.command == "principle" and args.principle_command == "test-skill":
            result = principles_service.test_skill(
                candidate_id=args.candidate_id, prompt=args.prompt
            )
            print(f"candidate_id={result.candidate_id}")
            print(f"score={result.score}")
            print(f"passed={str(result.passed).lower()}")
            print("notes:")
            for note in result.notes:
                print(f"- {note}")
            return 0

        if args.command == "principle" and args.principle_command == "approve-skill":
            candidate = principles_service.approve_skill(args.candidate_id)
            print(f"approved_candidate={candidate.candidate_id}")
            print(f"status={candidate.status.value}")
            return 0

        if args.command == "principle" and args.principle_command == "deploy":
            result = principles_service.deploy_approved_principles(targets=args.target)
            print(f"bundle_path={result.bundle_path}")
            print("modified_files:")
            if not result.modified_files:
                print("- none")
            else:
                for path in result.modified_files:
                    print(f"- {path}")
            return 0

        if args.command == "daily" and args.daily_command == "score":
            task_sources = args.task_source or _default_task_sources()
            tasks = daily_service.load_tasks(task_sources)
            scores = daily_service.score_tasks(tasks, daily_budget_minutes=args.daily_budget)
            print(_format_candidate_scores(scores))
            return 0

        if args.command == "daily" and args.daily_command == "run":
            task_sources = args.task_source or _default_task_sources()
            context_sources = args.context_source or _default_context_sources()

            repo_state = RepoState(
                is_clean=args.repo_clean,
                root_path=args.repo_path,
            )

            result = daily_service.run_daily_feature_implementer(
                task_sources=task_sources,
                context_sources=context_sources,
                repo_state=repo_state,
                client=args.client,
                force=args.force,
                daily_budget_minutes=args.daily_budget,
                task_risk=args.task_risk,
                max_file_changes=args.max_file_changes,
                simulate_changed_files=args.changed_file,
                tests_passed=args.tests_passed,
            )

            if args.workspace:
                # Optional manual override for demo/debug parity.
                result.workspace_type = WorkspaceType(args.workspace)

            print(render_daily_result(result))
            return 0

    except (FlowError, ValueError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2

    parser.print_help()
    return 1


def render_table(rows: list[dict[str, str]]) -> str:
    if not rows:
        return "No features found"

    columns = [
        "Feature",
        "Current phase",
        "Phase status",
        "Last update",
        "Open blockers",
        "Last conversation",
    ]
    widths = {
        col: max(len(col), *(len(str(row.get(col, ""))) for row in rows)) for col in columns
    }

    def format_row(row: dict[str, str]) -> str:
        return " | ".join(str(row.get(col, "")).ljust(widths[col]) for col in columns)

    separator = "-+-".join("-" * widths[col] for col in columns)
    output = [format_row({col: col for col in columns}), separator]
    output.extend(format_row(row) for row in rows)
    return "\n".join(output)


def _format_feature(feature) -> str:
    lines: list[str] = []
    lines.append(f"feature_id: {feature.feature_id}")
    lines.append(f"title: {feature.title}")
    lines.append(f"vision: {feature.vision}")
    lines.append(f"current_phase: {feature.current_phase.value}")
    lines.append(f"updated_at: {feature.updated_at.isoformat()}")
    lines.append("")

    for phase in feature.phases:
        lines.append(f"[{phase.phase.value}] status={phase.status.value}")
        lines.append(f"  artifacts={len(phase.artifacts)} feedback={len(phase.feedback)}")
        lines.append(f"  blockers={len(phase.blockers)} conversations={len(phase.conversations)}")
        if phase.code_links:
            lines.append("  code_links:")
            lines.extend(f"    - {item}" for item in phase.code_links)
        if phase.entry_points:
            lines.append("  entry_points:")
            lines.extend(f"    - {item}" for item in phase.entry_points)
        if phase.explanations:
            lines.append("  explanations:")
            lines.extend(f"    - {item}" for item in phase.explanations)

    return "\n".join(lines)


def _format_principles(notes) -> str:
    if not notes:
        return "No principles found"

    lines: list[str] = []
    for note in notes:
        lines.append(f"- {note.principle_id} [{note.status.value}] {note.title}")
        lines.append(f"  rule: {note.normalized_rule}")
        lines.append(f"  tags: {', '.join(note.tags) if note.tags else '-'}")
    return "\n".join(lines)


def _format_candidates(candidates) -> str:
    if not candidates:
        return "No skill candidates found"

    lines: list[str] = []
    for candidate in candidates:
        lines.append(
            f"- {candidate.candidate_id} [{candidate.status.value}] {candidate.name} ({candidate.target_scope.value})"
        )
        lines.append(f"  principles: {', '.join(candidate.principle_ids)}")
        if candidate.skill_path:
            lines.append(f"  skill_path: {candidate.skill_path}")
        if candidate.last_test_score is not None:
            lines.append(f"  last_test_score: {candidate.last_test_score}")
    return "\n".join(lines)


def _format_candidate_scores(scores) -> str:
    if not scores:
        return "No candidate scores"

    lines: list[str] = []
    for item in scores:
        lines.append(f"- {item.task_key}: {item.score}")
        lines.append(f"  reasons: {', '.join(item.reasons)}")
    return "\n".join(lines)


def _default_task_sources() -> list[str]:
    return [
        "dev/notes/ecosystem/tasks.md",
        "dev/notes/tasks.md",
    ]


def _default_context_sources() -> list[str]:
    return [
        "dev/notes",
        "README.md",
        "release/release.yaml",
    ]


def main() -> int:
    return run_cli()


if __name__ == "__main__":
    raise SystemExit(main())
