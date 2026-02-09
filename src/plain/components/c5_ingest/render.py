from __future__ import annotations

import json

from plain.components.c5_ingest.models import IngestedItem, ObsidianIngestResult


def render_ingest_result(result: ObsidianIngestResult) -> str:
    payload = {
        "run_id": result.run_id,
        "notes_scanned": result.notes_scanned,
        "items_created": result.items_created,
        "items_updated": result.items_updated,
        "low_confidence_items": [
            {
                "item_id": item.item_id,
                "confidence": item.confidence,
                "reason": item.reason,
            }
            for item in result.low_confidence_items
        ],
        "duplicate_candidates": [
            {
                "primary_id": item.primary_id,
                "duplicate_id": item.duplicate_id,
                "score": item.score,
                "reason": item.reason,
            }
            for item in result.duplicate_candidates
        ],
    }
    return json.dumps(payload, indent=2)


def render_items(items: list[IngestedItem]) -> str:
    if not items:
        return "No ingested items found"

    lines: list[str] = []
    for item in items:
        lines.append(f"- {item.item_id} [{item.kind.value}] {item.title}")
        lines.append(f"  confidence: {item.confidence}")
        lines.append(f"  refs: {len(item.source_refs)}")
        if item.tags:
            lines.append(f"  tags: {', '.join(item.tags)}")
    return "\n".join(lines)


def render_item_with_sources(item: IngestedItem) -> str:
    lines: list[str] = [
        f"item_id: {item.item_id}",
        f"kind: {item.kind.value}",
        f"title: {item.title}",
        f"description: {item.description}",
        f"confidence: {item.confidence}",
        f"approved: {str(item.approved).lower()}",
        "source_refs:",
    ]
    for source in item.source_refs:
        lines.append(f"- note_path: {source.note_path}")
        lines.append(f"  note_title: {source.note_title}")
        if source.heading:
            lines.append(f"  heading: {source.heading}")
        if source.excerpt:
            lines.append(f"  excerpt: {source.excerpt}")
    return "\n".join(lines)
