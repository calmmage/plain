---
project_id: prj_human_driven_ai_projects
project_name: c1-sample
repository_path: /Users/petrlavrov/work/projects/plain
tags:
- c1
- sample
created_at: '2026-02-09T06:00:00+00:00'
updated_at: '2026-02-09T06:20:00+00:00'
features:
- feature_id: feat_three_phase_flow_cli
  title: Three phase flow cli
  vision: Implement and track the 3-phase workflow
  current_phase: polish
  created_at: '2026-02-09T06:01:00+00:00'
  updated_at: '2026-02-09T06:20:00+00:00'
  completed_at: null
  phases:
  - phase: make_it_work
    status: done
    started_at: '2026-02-09T06:01:00+00:00'
    finished_at: '2026-02-09T06:08:00+00:00'
    owner: human+ai
    entry_criteria:
    - have PRD and desired UX
    exit_criteria:
    - demo command works
    artifacts:
    - kind: demo
      path: dev/notes/demos/c1.md
      note: entry: make demo-c1
    conversations:
    - client: codex
      session_id: c1-seed-session
      cwd: /Users/petrlavrov/work/projects/plain
      summary: Build c1 baseline
      linked_at: '2026-02-09T06:07:00+00:00'
    feedback: []
    blockers: []
    code_links:
    - src/plain/cli.py
    entry_points:
    - make demo-c1
    explanations:
    - First vertical slice, local-only persistence.
  - phase: test
    status: done
    started_at: '2026-02-09T06:08:00+00:00'
    finished_at: '2026-02-09T06:14:00+00:00'
    owner: human+ai
    entry_criteria: []
    exit_criteria:
    - at least one feedback cycle captured
    artifacts: []
    conversations: []
    feedback:
    - Board view is readable and actionable.
    blockers: []
    code_links:
    - src/plain/components/c1_flow/service.py
    entry_points:
    - uv run python src/main.py board c1-sample
    explanations:
    - Captures usability comments before polish.
  - phase: polish
    status: active
    started_at: '2026-02-09T06:14:00+00:00'
    finished_at: null
    owner: human+ai
    entry_criteria: []
    exit_criteria:
    - readme + deploy note attached
    artifacts:
    - kind: readme
      path: README.md
      note: c1 usage section
    conversations: []
    feedback: []
    blockers: []
    code_links:
    - Makefile
    entry_points:
    - make demo-c1
    explanations:
    - Finalize docs and handoff.
---

# c1-sample

- committed sample flow file for c1 fixture and manual exploration.
