.PHONY: setup run test demo-c1

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
