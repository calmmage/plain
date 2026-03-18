Project name: plain

Scope source:
- PRDs copied to `/Users/petrlavrov/work/projects/plain/dev/notes/prds/human-driven-ai-projects/`

Execution model:
- Build components strictly in PRD order.
- One branch per component.
- Branches are stacked (each next branch starts from previous branch tip).
- Commit continuously in small logical chunks.
- End every branch with a working demo command and short UX walkthrough.

Branch sequence (stacked):
1) `codex/c1-three-phase-flow`
   - Implements PRD 1 core models + state machine + basic CLI.
   - Must end with `make demo-c1`.
2) `codex/c2-release-flow`
   - Implements PRD 2 release spec + dry-run/launch scaffolding.
   - Base: `codex/c1-three-phase-flow`.
   - Must end with `make demo-c2`.
3) `codex/c3-principles-skills`
   - Implements PRD 3 principle capture + promote-to-skill flow.
   - Base: `codex/c2-release-flow`.
   - Must end with `make demo-c3`.
4) `codex/c4-daily-implementer`
   - Implements PRD 4 selector + workspace decision + execution packet.
   - Base: `codex/c3-principles-skills`.
   - Must end with `make demo-c4`.
5) `codex/c5-obsidian-ingest`
   - Implements PRD 5 ingestion + backlinks + entity store.
   - Base: `codex/c4-daily-implementer`.
   - Must end with `make demo-c5`.
6) `codex/c6-review-ui`
   - Implements PRD 6 review queue API + initial UI/CLI review surface.
   - Base: `codex/c5-obsidian-ingest`.
   - Must end with `make demo-c6`.
7) `codex/c7-bootstrap-scenarios`
   - Implements PRD 7 scenario registry + runner.
   - Base: `codex/c6-review-ui`.
   - Must end with `make demo-c7`.
8) `codex/c8-integrated-system`
   - Implements PRD 8 orchestration glue + global status command.
   - Base: `codex/c7-bootstrap-scenarios`.
   - Must end with `make demo-c8`.

Per-branch definition of done:
- Feature code + tests are green.
- README section updated for that component.
- Add demo target `demo-cX` to Makefile.
- Add showcase doc: `dev/notes/demos/cX.md` with:
  - purpose
  - exact command(s)
  - expected output
  - 3-7 step UX flow for manual test
- Add at least one realistic fixture/sample data for the component.

Commit rhythm:
- Commit after each sub-milestone:
  - data model
  - service logic
  - CLI/API surface
  - tests
  - docs/demo
- Prefer explicit messages like:
  - `c1: add phase models and validation rules`
  - `c1: add flow CLI start/advance commands`
  - `c1: add demo-c1 and walkthrough docs`

Suggested initial repo structure:
- `src/plain/core/` (shared models/state/events)
- `src/plain/components/c1_flow/`
- `src/plain/components/c2_release/`
- `src/plain/components/c3_principles/`
- `src/plain/components/c4_daily_runner/`
- `src/plain/components/c5_ingest/`
- `src/plain/components/c6_review/`
- `src/plain/components/c7_bootstrap/`
- `src/plain/components/c8_orchestrator/`
- `src/plain/cli.py`
- `tests/components/`
- `dev/notes/demos/`

Makefile demo target contract:
- `demo-c1` ... `demo-c8` must run without hidden setup.
- If env vars are required, demo target must print missing keys clearly and exit non-zero.
- Each demo target should run in <= 2 minutes.

Order of implementation inside each component:
1) minimal working prototype path
2) production path integrated into `src/plain`
3) tests
4) docs + demo target

Review checkpoints:
- After c1, c4, c6, c8 run a manual product review against PRDs.
- If scope drifts, update PRD note first, then code.

Non-goals for early phases:
- No premature full UI polishing before c6.
- No deployment automation before c2 baseline exists.
- No broad refactors during c1-c3 unless blocking.

Quick start for branch 1:
- `git checkout -b codex/c1-three-phase-flow`
- implement minimal c1 path
- add `make demo-c1`
- write `dev/notes/demos/c1.md`
- commit in increments
