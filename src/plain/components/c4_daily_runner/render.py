from __future__ import annotations

import json

from plain.components.c4_daily_runner.models import DailyJobResult


def render_daily_result(result: DailyJobResult) -> str:
    payload = {
        "selected_task": result.selected_task,
        "workspace_type": result.workspace_type.value,
        "workspace_path": result.workspace_path,
        "client": result.client,
        "session_id": result.session_id,
        "changed_files": result.changed_files,
        "review_packet": result.review_packet,
        "execution_log": result.execution_log,
        "status": result.status.value,
        "score_breakdown": [
            {
                "task_key": item.task_key,
                "score": item.score,
                "reasons": item.reasons,
            }
            for item in result.score_breakdown
        ],
    }
    return json.dumps(payload, indent=2)
