---
project_id: prj_human_driven_ai_projects
project_name: human-driven-ai-projects
repository_path: /Users/petrlavrov/work/projects/plain
tags:
- workflow
- c1
created_at: '2026-02-09T06:00:00+00:00'
updated_at: '2026-02-09T06:15:00+00:00'
features:
- feature_id: feat_three_phase_cli
  title: Three phase CLI
  vision: Build and maintain project/feature flow state from terminal.
  current_phase: test
  created_at: '2026-02-09T06:01:00+00:00'
  updated_at: '2026-02-09T06:15:00+00:00'
  completed_at: null
  phases:
  - phase: make_it_work
    status: done
    started_at: '2026-02-09T06:01:00+00:00'
    finished_at: '2026-02-09T06:10:00+00:00'
    owner: human+ai
    entry_criteria:
    - PRD exists
    exit_criteria:
    - demo runs
    artifacts:
    - kind: demo
      path: dev/notes/demos/c1.md
      note: entry: make demo-c1
    conversations:
    - client: codex
      session_id: s1-demo
      cwd: /Users/petrlavrov/work/projects/plain
      summary: Implement initial CLI
      linked_at: '2026-02-09T06:09:00+00:00'
    feedback: []
    blockers: []
    code_links:
    - src/plain/cli.py
    entry_points:
    - make demo-c1
    explanations:
    - Minimal vertical slice for c1
  - phase: test
    status: active
    started_at: '2026-02-09T06:11:00+00:00'
    finished_at: null
    owner: human+ai
    entry_criteria: []
    exit_criteria: []
    artifacts: []
    conversations: []
    feedback:
    - Clarify board output columns.
    blockers: []
    code_links: []
    entry_points: []
    explanations:
    - Collect human usability notes.
  - phase: polish
    status: todo
    started_at: null
    finished_at: null
    owner: human+ai
    entry_criteria: []
    exit_criteria: []
    artifacts: []
    conversations: []
    feedback: []
    blockers: []
    code_links: []
    entry_points: []
    explanations: []
---

# human-driven-ai-projects

- sample fixture for c1 tests and manual demos.
