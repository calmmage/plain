from pathlib import Path

from plain.components.c4_daily_runner.models import ContentOrigin, DailyTask, RepoState, WorkspaceType
from plain.components.c4_daily_runner.service import DailyImplementerService


def _service(tmp_path: Path) -> DailyImplementerService:
    return DailyImplementerService(
        workspace=tmp_path,
        review_dir=Path("dev/notes/ecosystem/review_packets"),
        log_dir=Path("dev/notes/ecosystem/daily_runs"),
    )


def test_score_prefers_simple_low_risk_task(tmp_path: Path) -> None:
    service = _service(tmp_path)
    tasks = service.load_tasks([Path("tests/fixtures/c4/tasks.md")])

    scores = service.score_tasks(tasks, daily_budget_minutes=180)
    assert scores[0].task_key == "al"
    assert "simple" in scores[0].reasons


def test_workspace_policy_variants(tmp_path: Path) -> None:
    service = _service(tmp_path)

    low_risk_task = DailyTask(key="a", title="A", risk="low")
    idea_task = DailyTask(key="b", title="B", risk="low", idea=True)

    assert (
        service.choose_workspace(low_risk_task, RepoState(is_clean=True, root_path="/tmp"))
        == WorkspaceType.MAIN_REPO
    )
    assert (
        service.choose_workspace(DailyTask(key="c", title="C", risk="high"), RepoState(is_clean=False, root_path="/tmp"))
        == WorkspaceType.GIT_WORKTREE
    )
    assert (
        service.choose_workspace(idea_task, RepoState(is_clean=False, root_path="/tmp"))
        == WorkspaceType.NEW_REPO_FROM_TEMPLATE
    )


def test_collect_context_has_multiple_source_types(tmp_path: Path) -> None:
    service = _service(tmp_path)
    packet = service.collect_context(
        [
            Path("tests/fixtures/c4/obsidian_notes.md"),
            Path("tests/fixtures/c4/telegram_highlights.json"),
            Path("tests/fixtures/c4/bookmarks.json"),
        ]
    )

    assert len(packet.source_type_counts) >= 2
    assert packet.source_type_counts.get("telegram", 0) >= 1
    assert any(item.origin == ContentOrigin.HUMAN for item in packet.items)


def test_run_daily_feature_implementer_generates_outputs(tmp_path: Path) -> None:
    service = _service(tmp_path)

    result = service.run_daily_feature_implementer(
        task_sources=[Path("tests/fixtures/c4/tasks.md")],
        context_sources=[
            Path("tests/fixtures/c4/obsidian_notes.md"),
            Path("tests/fixtures/c4/telegram_highlights.json"),
        ],
        repo_state=RepoState(is_clean=False, root_path=str(tmp_path)),
        client="codex",
        daily_budget_minutes=180,
        simulate_changed_files=["src/plain/components/c4_daily_runner/service.py"],
        tests_passed=True,
    )

    assert result.selected_task == "al"
    assert result.workspace_type == WorkspaceType.GIT_WORKTREE
    assert Path(result.review_packet).exists()
    assert Path(result.execution_log).exists()
    assert result.status.value == "completed"


def test_run_marks_requires_attention_on_failed_tests(tmp_path: Path) -> None:
    service = _service(tmp_path)

    result = service.run_daily_feature_implementer(
        task_sources=[Path("tests/fixtures/c4/tasks.md")],
        context_sources=[
            Path("tests/fixtures/c4/obsidian_notes.md"),
            Path("tests/fixtures/c4/telegram_highlights.json"),
        ],
        repo_state=RepoState(is_clean=False, root_path=str(tmp_path)),
        client="codex",
        tests_passed=False,
    )

    assert result.status.value == "requires_attention"
