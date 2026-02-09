from __future__ import annotations

import argparse
import sys
from typing import Sequence

from plain.components.c1_flow.service import FlowService
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

    return parser


def run_cli(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    service = FlowService.create_default()

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


def main() -> int:
    return run_cli()


if __name__ == "__main__":
    raise SystemExit(main())
