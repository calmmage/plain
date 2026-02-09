from __future__ import annotations

import json
import re
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Iterable

from plain.components.c4_daily_runner.models import (
    CandidateScore,
    ContentOrigin,
    ContextItem,
    ContextPacket,
    DailyJobResult,
    DailyTask,
    JobStatus,
    RepoState,
    ReviewPacket,
    WorkspaceType,
    utc_now,
)
from plain.core.models import FlowError


@dataclass(slots=True)
class DailyImplementerService:
    workspace: Path = Path(".")
    review_dir: Path = Path("dev/notes/ecosystem/review_packets")
    log_dir: Path = Path("dev/notes/ecosystem/daily_runs")

    def load_tasks(self, task_sources: Iterable[str | Path]) -> list[DailyTask]:
        tasks: list[DailyTask] = []
        for source in task_sources:
            path = self._resolve(source)
            if not path.exists():
                continue

            if path.suffix.lower() == ".json":
                tasks.extend(self._load_tasks_from_json(path))
            else:
                tasks.extend(self._load_tasks_from_markdown(path))

        deduped: dict[str, DailyTask] = {}
        for task in tasks:
            deduped[task.key] = task
        return list(deduped.values())

    def score_task(
        self,
        task: DailyTask,
        now: datetime | None = None,
        daily_budget_minutes: int = 180,
    ) -> CandidateScore:
        now = now or utc_now()
        score = 0.0
        reasons: list[str] = []

        if task.simple:
            score += 3.0
            reasons.append("simple")

        if task.status in {"todo", "selected"}:
            score += 1.5
            reasons.append("open_status")

        postponed = _parse_date(task.postponed_until)
        if postponed and postponed.date() >= now.date():
            score -= 2.0
            reasons.append("postponed")

        if task.backlog:
            score -= 1.0
            reasons.append("backlog")

        if task.blocked:
            score -= 2.5
            reasons.append("blocked")

        if task.last_touched_at:
            age_days = (now.date() - task.last_touched_at.date()).days
            if age_days >= 14:
                score += 0.6
                reasons.append("stale_boost")

        if task.estimated_minutes <= daily_budget_minutes:
            score += 1.0
            reasons.append("budget_fit")
        else:
            score -= 1.5
            reasons.append("over_budget")

        risk = task.risk.lower().strip()
        if risk == "low":
            score += 0.8
            reasons.append("low_risk")
        elif risk == "high":
            score -= 0.8
            reasons.append("high_risk")

        return CandidateScore(task_key=task.key, score=round(score, 3), reasons=reasons)

    def score_tasks(
        self,
        tasks: Iterable[DailyTask],
        daily_budget_minutes: int = 180,
    ) -> list[CandidateScore]:
        scores = [self.score_task(task, daily_budget_minutes=daily_budget_minutes) for task in tasks]
        return sorted(scores, key=lambda item: (-item.score, item.task_key))

    def choose_workspace(
        self,
        task: DailyTask,
        repo_state: RepoState,
        task_risk: str | None = None,
    ) -> WorkspaceType:
        risk = (task_risk or task.risk or "medium").lower().strip()

        if repo_state.is_clean and risk == "low":
            return WorkspaceType.MAIN_REPO
        if risk in {"medium", "high"}:
            return WorkspaceType.GIT_WORKTREE
        if task.idea:
            return WorkspaceType.NEW_REPO_FROM_TEMPLATE
        return WorkspaceType.GIT_WORKTREE

    def detect_origin(self, item_text: str, metadata: dict[str, Any]) -> ContentOrigin:
        source = str(metadata.get("source", "")).lower()

        if source in {"telegram_manual", "obsidian_note", "bookmark_manual", "human_note"}:
            return ContentOrigin.HUMAN
        if source in {"ai_chat_output", "llm_generated", "assistant_note"}:
            return ContentOrigin.AI
        if source in {"mixed", "hybrid"}:
            return ContentOrigin.MIXED

        # fallback: AI markers
        lowered = item_text.lower()
        if "as an ai" in lowered or "language model" in lowered:
            return ContentOrigin.AI
        return ContentOrigin.UNKNOWN

    def collect_context(
        self,
        context_sources: Iterable[str | Path],
        max_items: int = 24,
        max_chars_per_item: int = 380,
    ) -> ContextPacket:
        collected: list[ContextItem] = []

        for source in context_sources:
            path = self._resolve(source)
            if not path.exists():
                continue

            if path.is_dir():
                for file in sorted(path.rglob("*.md"))[:12]:
                    collected.extend(self._collect_from_file(file, max_chars_per_item))
            else:
                collected.extend(self._collect_from_file(path, max_chars_per_item))

        deduped: list[ContextItem] = []
        seen: set[str] = set()
        for item in collected:
            key = _norm(item.text)
            if not key or key in seen:
                continue
            seen.add(key)
            item.origin = self.detect_origin(item.text, item.metadata)
            deduped.append(item)
            if len(deduped) >= max_items:
                break

        counts: dict[str, int] = {}
        for item in deduped:
            counts[item.source_type] = counts.get(item.source_type, 0) + 1

        summary = self._summarize_context(deduped)
        return ContextPacket(items=deduped, summary=summary, source_type_counts=counts)

    def run_daily_feature_implementer(
        self,
        task_sources: Iterable[str | Path],
        context_sources: Iterable[str | Path],
        repo_state: RepoState,
        client: str = "codex",
        force: bool = False,
        daily_budget_minutes: int = 180,
        task_risk: str | None = None,
        max_file_changes: int = 40,
        simulate_changed_files: Iterable[str] | None = None,
        tests_passed: bool = True,
    ) -> DailyJobResult:
        tasks = self.load_tasks(task_sources)
        if not tasks:
            raise FlowError("No candidate tasks found")

        scores = self.score_tasks(tasks, daily_budget_minutes=daily_budget_minutes)
        selected_score = scores[0]
        selected_task = next(task for task in tasks if task.key == selected_score.task_key)

        workspace_type = self.choose_workspace(selected_task, repo_state, task_risk=task_risk)
        workspace_path = self._workspace_path(selected_task, workspace_type, repo_state)

        context_packet = self.collect_context(context_sources)
        source_type_count = len(context_packet.source_type_counts)
        if source_type_count < 2 and not force:
            raise FlowError(
                "Context enrichment requires at least 2 source types. Use --force to override."
            )

        changed_files = [str(item) for item in (simulate_changed_files or [])]
        status = JobStatus.COMPLETED
        unresolved: list[str] = []

        if len(changed_files) > max_file_changes:
            status = JobStatus.REQUIRES_ATTENTION
            unresolved.append(
                f"Changed files exceeded threshold ({len(changed_files)} > {max_file_changes})"
            )

        if not tests_passed:
            status = JobStatus.REQUIRES_ATTENTION
            unresolved.append("Tests failed during daily loop")

        session_id = self._build_session_id(client, selected_task.key)
        review_packet = self._write_review_packet(
            selected_task,
            workspace_type,
            workspace_path,
            context_packet,
            changed_files,
            unresolved,
            status,
        )

        execution_log = self._write_execution_log(
            selected_task,
            workspace_type,
            workspace_path,
            client,
            session_id,
            changed_files,
            review_packet.path,
            scores,
            status,
            source_type_count,
        )

        return DailyJobResult(
            selected_task=selected_task.key,
            workspace_type=workspace_type,
            workspace_path=str(workspace_path),
            client=client,
            session_id=session_id,
            changed_files=changed_files,
            review_packet=str(review_packet.path),
            execution_log=str(execution_log),
            status=status,
            score_breakdown=scores,
        )

    def _load_tasks_from_json(self, path: Path) -> list[DailyTask]:
        try:
            payload = json.loads(path.read_text())
        except Exception:
            return []

        rows: list[dict[str, Any]] = []
        if isinstance(payload, list):
            rows = [item for item in payload if isinstance(item, dict)]
        elif isinstance(payload, dict):
            if isinstance(payload.get("tasks"), list):
                rows = [item for item in payload["tasks"] if isinstance(item, dict)]

        tasks: list[DailyTask] = []
        for idx, row in enumerate(rows, start=1):
            key = str(row.get("key") or row.get("task_key") or f"task_{idx}")
            tasks.append(
                DailyTask(
                    key=key,
                    title=str(row.get("title") or row.get("text") or key),
                    status=str(row.get("status", "todo")),
                    simple=bool(row.get("simple", False)),
                    blocked=bool(row.get("blocked", False)),
                    backlog=bool(row.get("backlog", False)),
                    idea=bool(row.get("idea", False)),
                    postponed_until=_as_optional_str(row.get("postponed_until")),
                    risk=str(row.get("risk", "medium")),
                    estimated_minutes=int(row.get("estimated_minutes", 90)),
                    source_path=str(path),
                    last_touched_at=_parse_datetime(_as_optional_str(row.get("last_touched_at"))),
                    metadata={k: v for k, v in row.items() if k not in {
                        "key",
                        "task_key",
                        "title",
                        "text",
                        "status",
                        "simple",
                        "blocked",
                        "backlog",
                        "idea",
                        "postponed_until",
                        "risk",
                        "estimated_minutes",
                        "last_touched_at",
                    }},
                )
            )
        return tasks

    def _load_tasks_from_markdown(self, path: Path) -> list[DailyTask]:
        lines = path.read_text().splitlines()
        tasks: list[DailyTask] = []
        pattern = re.compile(r"^\s*[-*]\s*\[(?P<done>[ xX])]\s+(?P<title>.+)$")

        for idx, line in enumerate(lines, start=1):
            match = pattern.match(line)
            if not match:
                continue

            raw_title = match.group("title").strip()
            status = "done" if match.group("done").lower() == "x" else "todo"
            attrs = self._parse_task_attributes(raw_title)
            title = attrs.pop("title")

            key = str(attrs.get("key") or f"task_{idx}")
            estimated = _as_int(attrs.get("estimate"), default=90)

            task = DailyTask(
                key=key,
                title=title,
                status=str(attrs.get("status", status)),
                simple=bool(attrs.get("simple", False)),
                blocked=bool(attrs.get("blocked", False)),
                backlog=bool(attrs.get("backlog", False)),
                idea=bool(attrs.get("idea", False)),
                postponed_until=_as_optional_str(attrs.get("postponed")),
                risk=str(attrs.get("risk", "medium")),
                estimated_minutes=estimated,
                source_path=str(path),
                last_touched_at=_parse_datetime(_as_optional_str(attrs.get("touched"))),
                metadata={"line": idx},
            )
            tasks.append(task)

        return tasks

    def _parse_task_attributes(self, text: str) -> dict[str, Any]:
        tokens = re.findall(r"\[(.+?)]", text)
        cleaned = re.sub(r"\s*\[.+?]", "", text).strip()
        attrs: dict[str, Any] = {"title": cleaned}

        for token in tokens:
            normalized = token.strip().lower()
            if normalized in {"simple", "blocked", "backlog", "idea"}:
                attrs[normalized] = True
                continue
            if ":" not in normalized:
                continue
            key, value = normalized.split(":", 1)
            attrs[key.strip()] = value.strip()

        return attrs

    def _collect_from_file(self, path: Path, max_chars_per_item: int) -> list[ContextItem]:
        suffix = path.suffix.lower()
        if suffix == ".json":
            return self._collect_from_json(path, max_chars_per_item)

        text = path.read_text(errors="ignore")
        snippet = text.strip().replace("\n", " ")[:max_chars_per_item]
        if not snippet:
            return []

        source_type = _infer_source_type(path)
        metadata = {"source": _infer_source_label(path)}
        return [
            ContextItem(
                source_type=source_type,
                source_path=str(path),
                text=snippet,
                metadata=metadata,
            )
        ]

    def _collect_from_json(self, path: Path, max_chars_per_item: int) -> list[ContextItem]:
        try:
            payload = json.loads(path.read_text())
        except Exception:
            return []

        source_type = _infer_source_type(path)
        source_label = _infer_source_label(path)

        items: list[ContextItem] = []
        if isinstance(payload, list):
            iterable = payload
        elif isinstance(payload, dict):
            iterable = payload.get("items") if isinstance(payload.get("items"), list) else [payload]
        else:
            iterable = []

        for row in iterable[:20]:
            if isinstance(row, dict):
                text = _as_optional_str(row.get("text")) or _as_optional_str(row.get("content"))
                if not text:
                    text = json.dumps(row, ensure_ascii=True)
                text = text.strip().replace("\n", " ")[:max_chars_per_item]
                if not text:
                    continue
                metadata = dict(row)
                metadata.setdefault("source", source_label)
                items.append(
                    ContextItem(
                        source_type=source_type,
                        source_path=str(path),
                        text=text,
                        metadata=metadata,
                    )
                )
            elif isinstance(row, str):
                text = row.strip().replace("\n", " ")[:max_chars_per_item]
                if text:
                    items.append(
                        ContextItem(
                            source_type=source_type,
                            source_path=str(path),
                            text=text,
                            metadata={"source": source_label},
                        )
                    )

        return items

    def _summarize_context(self, items: list[ContextItem], max_lines: int = 10) -> str:
        if not items:
            return "No context collected"

        grouped: dict[str, list[ContextItem]] = {}
        for item in items:
            grouped.setdefault(item.source_type, []).append(item)

        lines: list[str] = ["Context summary:"]
        for source_type in sorted(grouped.keys()):
            lines.append(f"- {source_type}:")
            for entry in grouped[source_type][:2]:
                snippet = entry.text[:120].strip()
                lines.append(f"  - {snippet}")
                if len(lines) >= max_lines:
                    return "\n".join(lines)

        return "\n".join(lines)

    def _workspace_path(
        self,
        task: DailyTask,
        workspace_type: WorkspaceType,
        repo_state: RepoState,
    ) -> Path:
        if workspace_type == WorkspaceType.MAIN_REPO:
            return Path(repo_state.root_path)

        if workspace_type == WorkspaceType.NEW_REPO_FROM_TEMPLATE:
            return self.workspace / "prototypes" / f"{task.key}"

        return self.workspace / "worktrees" / f"feature-{task.key}"

    def _build_session_id(self, client: str, task_key: str) -> str:
        stamp = utc_now().strftime("%Y%m%d%H%M%S")
        return f"{client}-{task_key}-{stamp}"

    def _write_review_packet(
        self,
        task: DailyTask,
        workspace_type: WorkspaceType,
        workspace_path: Path,
        context: ContextPacket,
        changed_files: list[str],
        unresolved: list[str],
        status: JobStatus,
    ) -> ReviewPacket:
        now = utc_now()
        self._resolve(self.review_dir).mkdir(parents=True, exist_ok=True)
        path = self._resolve(self.review_dir) / f"{now.date().isoformat()}-{task.key}.md"

        run_instructions = [
            "Run project tests before merge",
            "Reproduce changes locally in selected workspace",
        ]

        if status == JobStatus.REQUIRES_ATTENTION:
            run_instructions.append("Address unresolved issues before continuing")

        unresolved_questions = unresolved or ["No unresolved questions."]

        lines = [
            f"# Daily Review Packet - {task.key}",
            "",
            f"- status: {status.value}",
            f"- task: {task.title}",
            f"- workspace_type: {workspace_type.value}",
            f"- workspace_path: {workspace_path}",
            "",
            "## Summary",
            context.summary,
            "",
            "## Changed Files",
        ]

        if changed_files:
            lines.extend([f"- {item}" for item in changed_files])
        else:
            lines.append("- none (implementation loop placeholder)")

        lines.extend(["", "## Run/Test Instructions"])
        lines.extend([f"- {item}" for item in run_instructions])

        lines.extend(["", "## Unresolved Questions"])
        lines.extend([f"- {item}" for item in unresolved_questions])

        path.write_text("\n".join(lines).rstrip() + "\n")

        return ReviewPacket(
            path=path,
            summary=context.summary,
            changed_files=changed_files,
            run_instructions=run_instructions,
            unresolved_questions=unresolved_questions,
        )

    def _write_execution_log(
        self,
        task: DailyTask,
        workspace_type: WorkspaceType,
        workspace_path: Path,
        client: str,
        session_id: str,
        changed_files: list[str],
        review_packet_path: Path,
        scores: list[CandidateScore],
        status: JobStatus,
        source_type_count: int,
    ) -> Path:
        now = utc_now()
        self._resolve(self.log_dir).mkdir(parents=True, exist_ok=True)
        path = self._resolve(self.log_dir) / f"{now.date().isoformat()}-{task.key}.json"

        payload = {
            "job_name": "daily_feature_implementer",
            "timestamp": now.isoformat(),
            "selected_task": task.key,
            "selected_title": task.title,
            "workspace_type": workspace_type.value,
            "workspace_path": str(workspace_path),
            "client": client,
            "session_id": session_id,
            "changed_files": changed_files,
            "review_packet": str(review_packet_path),
            "status": status.value,
            "context_source_types": source_type_count,
            "score_breakdown": [
                {
                    "task_key": item.task_key,
                    "score": item.score,
                    "reasons": item.reasons,
                }
                for item in scores
            ],
        }
        path.write_text(json.dumps(payload, indent=2) + "\n")
        return path

    def _resolve(self, path: str | Path) -> Path:
        candidate = Path(path)
        if candidate.is_absolute():
            return candidate
        return self.workspace / candidate


def _infer_source_type(path: Path) -> str:
    lowered = str(path).lower()
    if "telegram" in lowered:
        return "telegram"
    if "bookmark" in lowered:
        return "bookmarks"
    if "obsidian" in lowered or path.suffix.lower() == ".md":
        return "obsidian"
    if "commit" in lowered or "diff" in lowered or "git" in lowered:
        return "recent_code"
    return "external"


def _infer_source_label(path: Path) -> str:
    source_type = _infer_source_type(path)
    if source_type == "telegram":
        return "telegram_manual"
    if source_type == "obsidian":
        return "obsidian_note"
    if source_type == "bookmarks":
        return "bookmark_manual"
    return "external_link"


def _norm(text: str) -> str:
    return " ".join(text.lower().split())


def _as_int(value: Any, default: int) -> int:
    try:
        return int(value)
    except Exception:
        return default


def _as_optional_str(value: Any) -> str | None:
    if value in (None, ""):
        return None
    return str(value)


def _parse_date(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value)
    except Exception:
        return None


def _parse_datetime(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value)
    except Exception:
        return None
