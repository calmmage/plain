.PHONY: setup run test demo-c1 release-plan release-dry-run release-launch release-rollback demo-c2 demo-c3 demo-c4 demo-c5 demo-c6

setup:
	uv sync --group extras --group test

run:
	uv run python src/main.py

test:
	uv run pytest src tests

demo-c1:
	@set -e
	uv run python src/main.py init c1-demo --repo "$$PWD"
	uv run python src/main.py feature add c1-demo "Three phase flow cli" --vision "Implement and track the 3-phase workflow" --feature-id feat_three_phase_flow_cli
	uv run python src/main.py phase start c1-demo feat_three_phase_flow_cli make_it_work
	uv run python src/main.py meta add c1-demo feat_three_phase_flow_cli --code-link src/plain/cli.py --entry-point "make demo-c1" --explanation "Initial c1 command surface"
	uv run python src/main.py artifact add c1-demo feat_three_phase_flow_cli --kind demo --path dev/notes/demos/c1.md --note "entry: make demo-c1"
	uv run python src/main.py phase advance c1-demo feat_three_phase_flow_cli
	uv run python src/main.py feedback add c1-demo feat_three_phase_flow_cli --text "Board columns are clear enough for a first pass"
	uv run python src/main.py phase advance c1-demo feat_three_phase_flow_cli
	uv run python src/main.py artifact add c1-demo feat_three_phase_flow_cli --kind readme --path README.md
	uv run python src/main.py artifact add c1-demo feat_three_phase_flow_cli --kind deploy_note --path dev/notes/demos/c1.md
	uv run python src/main.py conv link c1-demo feat_three_phase_flow_cli --client codex --session-id c1-demo-session --cwd "$$PWD" --summary "Demo conversation"
	uv run python src/main.py board c1-demo
	uv run python src/main.py snapshot c1-demo

release-plan:
	uv run python -m tools.release.cli plan

release-dry-run:
	uv run python -m tools.release.cli dry-run

release-launch:
	uv run python -m tools.release.cli launch --yes

release-rollback:
	uv run python -m tools.release.cli rollback

demo-c2:
	@set -e
	make release-plan
	make release-dry-run
	uv run python -m tools.release.cli launch --yes
	make release-rollback

demo-c3:
	@set -e; \
	P_ID=$$(uv run python -m tools.workflow.principles.cli capture --title "Keep docs pointer-only" --raw "details in linked files, keep coordinator docs concise" --source "$$PWD/dev/notes/demos/c3.md" --rationale "Avoid instruction bloat by linking out details." --example-good "Reference docs by path and keep top-level instructions concise." --example-bad "Inline all details in every coordinator file." --tag workflow --tag docs | awk -F= '/captured_principle=/{print $$2}'); \
	C_ID=$$(uv run python -m tools.workflow.principles.cli promote "$$P_ID" --skill-name concise-coordinator --scope coding | awk -F= '/candidate_id=/{print $$2}'); \
	uv run python -m tools.workflow.principles.cli test-skill "$$C_ID" --prompt "Validate concise coordinator behavior for coding tasks"; \
	uv run python -m tools.workflow.principles.cli approve-skill "$$C_ID"; \
	uv run python -m tools.workflow.principles.cli deploy --target AGENTS.md --target CLAUDE.md --target GEMINI.md; \
	uv run python -m tools.workflow.principles.cli list --status approved; \
	uv run python -m tools.workflow.principles.cli list-candidates --status approved

demo-c4:
	@set -e
	uv run python -m tools.workflow.daily_runner.cli score --task-source dev/notes/ecosystem/daily_inputs/tasks_sample.md --daily-budget 180
	uv run python -m tools.workflow.daily_runner.cli run \
		--task-source dev/notes/ecosystem/daily_inputs/tasks_sample.md \
		--context-source dev/notes/ecosystem/daily_inputs/obsidian_context.md \
		--context-source dev/notes/ecosystem/daily_inputs/telegram_context.json \
		--context-source dev/notes/ecosystem/daily_inputs/bookmarks_context.json \
		--repo-path "$$PWD" \
		--client codex \
		--changed-file src/plain/components/c4_daily_runner/service.py

demo-c5:
	@set -e
	uv run python -m tools.workflow.obsidian_ingest.cli run \
		--note-root tests/fixtures/c5/obsidian/daily \
		--note-root tests/fixtures/c5/obsidian/preproject \
		--note-root tests/fixtures/c5/obsidian/workalongs \
		--note-root tests/fixtures/c5/obsidian/dumps \
		--force-full-scan
	uv run python -m tools.workflow.obsidian_ingest.cli list --min-confidence 0.6
	uv run python -m tools.workflow.obsidian_ingest.cli pending

demo-c6:
	@set -e
	uv run python -m tools.workflow.review_ui.cli ingest \
		--packet-path tests/fixtures/c6/review_packets/2026-02-09-al.md \
		--project-id prj_plain \
		--feature-id feat_review_ui \
		--original-vision "Provide one review workspace with runnable instructions and concise vision reminder."
	uv run python -m tools.workflow.review_ui.cli ingest \
		--packet-path tests/fixtures/c6/review_packets/manual_items.json
	uv run python -m tools.workflow.review_ui.cli list --ready-only
