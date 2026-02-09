from __future__ import annotations

import json

from plain.components.c6_review.models import FeedbackEntry, ReviewIngestResult, ReviewInstruction, ReviewItem


def render_ingest_result(result: ReviewIngestResult) -> str:
    return json.dumps(
        {
            "packets_scanned": result.packets_scanned,
            "items_created": result.items_created,
            "items_updated": result.items_updated,
            "blocked_items": result.blocked_items,
        },
        indent=2,
    )


def render_review_table(items: list[ReviewItem]) -> str:
    if not items:
        return "No review items found"

    columns = [
        "Status",
        "Project",
        "Feature",
        "Summary",
        "Original vision",
        "How to run",
        "Changed files",
        "Updated",
    ]

    rows: list[dict[str, str]] = []
    for item in items:
        first_instruction = item.run_instructions[0].command if item.run_instructions else "-"
        rows.append(
            {
                "Status": item.status.value,
                "Project": item.project_id,
                "Feature": item.feature_id,
                "Summary": _truncate(item.summary, 60),
                "Original vision": _truncate(item.original_vision or "-", 60),
                "How to run": _truncate(first_instruction, 40),
                "Changed files": str(len(item.changed_files)),
                "Updated": item.updated_at.isoformat(),
            }
        )

    widths = {
        col: max(len(col), *(len(row[col]) for row in rows))
        for col in columns
    }

    def _format_row(row: dict[str, str]) -> str:
        return " | ".join(row[col].ljust(widths[col]) for col in columns)

    header = _format_row({col: col for col in columns})
    separator = "-+-".join("-" * widths[col] for col in columns)
    body = [_format_row(row) for row in rows]
    return "\n".join([header, separator, *body])


def render_review_item(item: ReviewItem, feedback_entries: list[FeedbackEntry]) -> str:
    lines = [
        f"review_id: {item.review_id}",
        f"status: {item.status.value}",
        f"project_id: {item.project_id}",
        f"feature_id: {item.feature_id}",
        f"task_key: {item.task_key or '-'}",
        f"original_vision: {item.original_vision or '-'}",
        f"summary: {item.summary}",
        f"updated_at: {item.updated_at.isoformat()}",
        "",
        "run_instructions:",
    ]

    if item.run_instructions:
        for idx, instruction in enumerate(item.run_instructions, start=1):
            lines.append(f"- [{idx}] {instruction.title}")
            lines.append(f"  command: {instruction.command}")
            lines.append(f"  cwd: {instruction.cwd}")
            if instruction.expected_result:
                lines.append(f"  expected: {instruction.expected_result}")
    else:
        lines.append("- none")

    lines.append("")
    lines.append("changed_files:")
    lines.extend([f"- {path}" for path in item.changed_files] or ["- none"])

    lines.append("")
    lines.append("source_refs:")
    lines.extend([f"- {path}" for path in item.source_refs] or ["- none"])

    lines.append("")
    lines.append("conversation_refs:")
    lines.extend([f"- {ref}" for ref in item.conversation_refs] or ["- none"])

    lines.append("")
    lines.append("feedback_history:")
    if feedback_entries:
        for entry in feedback_entries:
            lines.append(
                f"- {entry.created_at.isoformat()} {entry.author} [{entry.verdict.value}] {entry.notes}"
            )
            if entry.tags:
                lines.append(f"  tags: {', '.join(entry.tags)}")
    else:
        lines.append("- none")

    return "\n".join(lines)


def render_instruction(instruction: ReviewInstruction) -> str:
    lines = [
        f"title: {instruction.title}",
        f"command: {instruction.command}",
        f"cwd: {instruction.cwd}",
    ]
    if instruction.expected_result:
        lines.append(f"expected_result: {instruction.expected_result}")
    return "\n".join(lines)


def _truncate(text: str, limit: int) -> str:
    value = text.replace("\n", " ").strip()
    if len(value) <= limit:
        return value
    return value[: limit - 3].rstrip() + "..."
