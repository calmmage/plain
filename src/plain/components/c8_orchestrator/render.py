from __future__ import annotations

import json

from plain.components.c8_orchestrator.models import WorkflowStatusSnapshot


def render_workflow_status(snapshot: WorkflowStatusSnapshot) -> str:
    lines = [
        f"generated_at: {snapshot.generated_at.isoformat()}",
        "modules:",
    ]
    for module in snapshot.modules:
        lines.append(f"- {module.module_id} {module.title} [{module.status}]")
        lines.append(f"  details: {json.dumps(module.details, ensure_ascii=True, sort_keys=True)}")
    return "\n".join(lines)
