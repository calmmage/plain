# PRD 4: Daily automation that picks and implements project features

Source: `/Users/petrlavrov/calmmage/obsidian/Inbox/Human-driven AI projects.md`

Raw source excerpt (verbatim):

-> daily job automation that picks a project / feature for a project -> implements that
Option 1: in a git worktree
Option 2: in a new dir or repo (from template? Ai picks?)
Option 3: in the main repo? How to decide? Well, if there’s no diff in the current repo - why not?

References:
My “local job runner”
My “dev_task_manader” task start command using claude sdk
- Todo: enrich tasks with context from new obsidian notes, telegram/bookmarks, newly deployed systems, ai trends, TikTok UI references, new code files, and filter out human input from ai-generated text

## Goal

Run one focused daily implementation cycle that:
- picks a high-value, clear feature task,
- selects an execution workspace (worktree/new repo/main repo),
- starts an AI coding session with rich context,
- saves artifacts for human review.

## Existing references

- `/Users/petrlavrov/calmmage/tools/automations/new_local_job_runner/cli.py`
- `/Users/petrlavrov/calmmage/tools/automations/new_local_job_runner/job_runner.py`
- `/Users/petrlavrov/calmmage/tools/task_management/dev_task_manager/task_start.py`
- `/Users/petrlavrov/calmmage/tools/task_management/dev_task_manager/task_sampling.py`
- `/Users/petrlavrov/calmmage/dev/notes/ecosystem/tasks.md`
- `/Users/petrlavrov/calmmage/calmlib/telegram/telegram_cache.py`
- `/Users/petrlavrov/calmmage/calmlib/utils/chrome_bookmarks.py`

## Scope

In scope:
- Daily selector job.
- Workspace decision policy.
- Context enrichment pipeline.
- Annotation and review packet generation.

Out of scope:
- Fully autonomous merge-to-main without human review.

## Job contract

Job name suggestion: `daily_feature_implementer`

Inputs:
- global ecosystem task pool
- local tool task pools
- context sources (obsidian/telegram/bookmarks/recent commits)

Outputs:
- execution log
- branch/worktree/repo path
- AI session ids
- artifact bundle for review UI

## Candidate scoring

Task score factors:
- `simple` flag boost
- recent relevance boost
- blocked penalty
- stale mild boost (to unstick backlog)
- estimated duration within daily budget

```python
from dataclasses import dataclass

@dataclass
class CandidateScore:
    task_key: str
    score: float
    reasons: list[str]


def score_task(task) -> CandidateScore:
    score = 0.0
    reasons = []

    if getattr(task, "simple", False):
        score += 3.0
        reasons.append("simple")
    if task.status in {"todo", "selected"}:
        score += 1.5
    if getattr(task, "postponed_until", None):
        score -= 2.0
        reasons.append("postponed")
    if getattr(task, "backlog", False):
        score -= 1.0
        reasons.append("backlog")

    return CandidateScore(task_key=task.key, score=score, reasons=reasons)
```

## Workspace decision policy

Decision order:
1. Use main repo only if clean working tree and task is low-risk/local.
2. Use worktree for normal feature implementation.
3. Use new repo/directory for prototype or architecture exploration.

```python
def choose_workspace(task, repo_state, task_risk: str) -> str:
    if repo_state.is_clean and task_risk == "low":
        return "main_repo"
    if task_risk in {"medium", "high"}:
        return "git_worktree"
    if getattr(task, "idea", False):
        return "new_repo_from_template"
    return "git_worktree"
```

## Context enrichment pipeline

Sources:
- Obsidian recent notes (`daily`, `preproject`, `workalongs`, `dumps`)
- Telegram highlights/messages
- Bookmarks/articles
- Recent code diffs and commits

Pipeline stages:
- collect
- deduplicate
- classify (`human_input`, `ai_generated`, `mixed`, `external_link`)
- summarize for coding prompt

Human-vs-AI text filter:

```python
class ContentOrigin(str, Enum):
    HUMAN = "human"
    AI = "ai"
    MIXED = "mixed"
    UNKNOWN = "unknown"


def detect_origin(item_text: str, metadata: dict) -> ContentOrigin:
    if metadata.get("source") in {"telegram_manual", "obsidian_note"}:
        return ContentOrigin.HUMAN
    if metadata.get("source") in {"ai_chat_output", "llm_generated"}:
        return ContentOrigin.AI
    # fallback heuristic omitted
    return ContentOrigin.UNKNOWN
```

## Execution flow

1. Build candidate pool.
2. Score and pick one feature task.
3. Decide workspace type.
4. Gather enriched context packet.
5. Start AI session (claude/codex/gemini based on task metadata).
6. Run bounded implementation loop.
7. Produce review packet:
   - summary
   - changed files
   - run/test instructions
   - unresolved questions

## CLI/API contract

Command examples:
- `uv run typer tools/automations/new_local_job_runner/cli.py run daily_feature_implementer`
- `... run daily_feature_implementer --force`

Job result detailed payload:

```json
{
  "selected_task": "al",
  "workspace_type": "git_worktree",
  "workspace_path": "/Users/.../worktrees/feature-al",
  "client": "claude",
  "session_id": "abc123...",
  "changed_files": ["tools/x.py", "docs/y.md"],
  "review_packet": "/Users/.../dev/notes/ecosystem/review_packets/2026-02-09-al.md"
}
```

## Safety rails

- Max runtime per daily loop.
- Max file-change count threshold before forced human checkpoint.
- Never auto-merge or auto-deploy.
- If tests fail, mark `REQUIRES_ATTENTION` and stop.

## Acceptance criteria

- Daily job picks one task and logs scoring reasons.
- Workspace decision is deterministic and auditable.
- Prompt includes enriched context from at least 2 source types.
- Job returns review packet with run instructions.
- Failures are captured with actionable error notes.

## Implementation plan

Phase A:
- Build selector + scoring + workspace chooser.
- Hook into existing runner registry.

Phase B:
- Add context enrichment collectors.
- Add origin classification and source confidence.

Phase C:
- Add review packet writer and integration with review UI queue.

## Risks and mitigations

- Risk: wrong task gets selected repeatedly.
  - Mitigation: recency cooldown and diversity penalty.
- Risk: enrichment noise overwhelms prompt.
  - Mitigation: strict token budget and top-k source snippets.
- Risk: too many changes from one job.
  - Mitigation: hard cap + checkpoint stop.

## Open questions

- Preferred default AI client for this job?
- Should this run every day or only weekdays?
- Should selection include only tasks from `ecosystem/tasks.md` or all task stores?
