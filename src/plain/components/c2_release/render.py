from __future__ import annotations

from pathlib import Path

from plain.components.c2_release.models import DryRunReport, GateCheckResult, ReleaseRunbook


def render_runbook(runbook: ReleaseRunbook) -> str:
    lines: list[str] = []
    lines.append(f"release={runbook.spec.service}:{runbook.spec.version}")
    lines.append(f"type={runbook.spec.release_type}")
    lines.append("")
    for step in runbook.steps:
        lines.append(f"- {step.id}: {step.title}")
        lines.append(f"  {step.description}")
        if step.command:
            lines.append(f"  cmd: {step.command}")
        if step.requires_human_approval:
            lines.append("  human_approval: required")
    return "\n".join(lines)


def render_dry_run_report(report: DryRunReport) -> str:
    rows: list[dict[str, str]] = []
    for check in report.checks:
        rows.append(
            {
                "Gate": check.gate,
                "Required": "yes" if check.required else "no",
                "Result": "PASS" if check.passed else "FAIL",
                "Details": check.details,
            }
        )

    lines = [
        f"release={report.spec.service}:{report.spec.version}",
        f"state={report.state.value}",
        "",
        render_table(rows),
        "",
        "db_gate:",
        f"  backup_ok={str(report.db_gate.backup_ok).lower()}",
        f"  dry_run_ok={str(report.db_gate.dry_run_ok).lower()}",
        f"  smoke_ok={str(report.db_gate.smoke_ok).lower()}",
        f"  rollback_tested={str(report.db_gate.rollback_tested).lower()}",
    ]
    return "\n".join(lines)


def render_table(rows: list[dict[str, str]]) -> str:
    if not rows:
        return "No checks"

    columns = ["Gate", "Required", "Result", "Details"]
    widths = {
        col: max(len(col), *(len(str(row.get(col, ""))) for row in rows)) for col in columns
    }

    def as_line(row: dict[str, str]) -> str:
        return " | ".join(str(row.get(col, "")).ljust(widths[col]) for col in columns)

    header = as_line({col: col for col in columns})
    sep = "-+-".join("-" * widths[col] for col in columns)
    body = [as_line(row) for row in rows]
    return "\n".join([header, sep, *body])


def render_launch_pack(paths: list[str | Path]) -> str:
    lines = ["generated launch pack files:"]
    lines.extend([f"- {path}" for path in paths])
    return "\n".join(lines)


def render_gate_failures(checks: list[GateCheckResult]) -> str:
    failed = [check.gate for check in checks if check.required and not check.passed]
    if not failed:
        return "all critical gates passed"
    return "failed gates: " + ", ".join(failed)
