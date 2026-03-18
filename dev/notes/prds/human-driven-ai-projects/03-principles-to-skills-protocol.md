# PRD 3: Capture guiding principles into skills/protocols

Source: `/Users/petrlavrov/calmmage/obsidian/Inbox/Human-driven AI projects.md`

Raw source excerpt (verbatim):

- a nice way for our tool to capture guiding principles into its “skills” library witb specific code / user flow - during working with the user
- A quick ai-based command / dwscribed flow / protocol which says
Reference: my “ai character” tool / automation and my LLM_rules based promt deloyment automation (find in tools/automations I think)

## Goal

Turn repeated human guidance patterns into reusable, reviewable skill assets and deployable AI instruction fragments.

## Existing references

- `/Users/petrlavrov/calmmage/tools/misc/ai_character_launcher/launcher.sh`
- `/Users/petrlavrov/calmmage/resources/ai_character_launcher/characters/`
- `/Users/petrlavrov/calmmage/tools/automations/ai_instructions_composer/cli.py`
- `/Users/petrlavrov/calmmage/scripts/new_daily_jobs/ai_instructions_sync.py`
- `/Users/petrlavrov/calmmage/LLM_RULES.md`

## Problem

Good principles appear in chat and disappear. You want:
- Fast capture during active work.
- Structured storage and versioning.
- Easy promotion to reusable skill or instruction rule.

## Scope

In scope:
- Principle capture schema.
- Promotion workflow: note -> candidate -> approved skill.
- CLI protocol for quick capture and review.
- Integration into instruction deployment.

Out of scope:
- Automatic publishing to public marketplaces.
- Full NLP mining across all historical chats in v1.

## Data model

```python
from datetime import datetime
from pydantic import BaseModel, Field


class PrincipleNote(BaseModel):
    principle_id: str
    title: str
    raw_quote: str
    normalized_rule: str
    rationale: str
    example_good: str | None = None
    example_bad: str | None = None
    source_path: str
    source_session_id: str | None = None
    tags: list[str] = Field(default_factory=list)
    created_at: datetime


class SkillCandidate(BaseModel):
    candidate_id: str
    name: str
    principle_ids: list[str]
    target_scope: str  # coding|release|review|ux
    status: str  # draft|review|approved|rejected
    skill_path: str | None = None
    test_prompt: str | None = None
```

## Filesystem layout

- Capture inbox:
  - `/Users/petrlavrov/calmmage/dev/notes/ecosystem/principles/inbox/`
- Reviewed principles:
  - `/Users/petrlavrov/calmmage/dev/notes/ecosystem/principles/approved/`
- Skill candidates:
  - `/Users/petrlavrov/calmmage/dev/notes/ecosystem/principles/candidates/`
- Generated skills:
  - `/Users/petrlavrov/.codex/skills/local/` (or repository-local skill folder)

## Quick command protocol

CLI examples:
- `principle capture --title "Prefer pointer-only docs" --raw "..." --source /path/file.md`
- `principle list --status draft`
- `principle promote <principle_id> --skill-name concise-coordinator`
- `principle test-skill <skill_id> --prompt "..."`
- `principle approve-skill <skill_id>`

## Capture format

Example markdown note:

```markdown
---
principle_id: pr_2026_02_09_01
tags: [workflow, focus, docs]
source_path: /Users/petrlavrov/calmmage/obsidian/Inbox/Human-driven AI projects.md
source_session_id:
status: draft
---

raw_quote: "details in linked files, keep coordinator docs concise"

normalized_rule:
Keep coordinator docs pointer-only; move details to linked docs.

rationale:
Reduces cognitive overload and keeps execution-oriented navigation quick.
```

## Promotion to skill asset

Generated `SKILL.md` sections:
- intent
- trigger conditions
- step protocol
- output contract
- anti-patterns
- examples

Generation skeleton:

```python
def build_skill_markdown(name: str, principles: list[PrincipleNote]) -> str:
    rules = "\n".join([f"- {p.normalized_rule}" for p in principles])
    return f"""# {name}\n\n## Trigger\nUse when scope matches captured principles.\n\n## Protocol\n{rules}\n\n## Validation\n- Output is concise\n- Output includes file pointers\n"""
```

## Review loop

1. Capture principle from active work.
2. Normalize to one actionable rule sentence.
3. Attach at least one example.
4. Generate skill candidate.
5. Run test prompts.
6. Approve and deploy via instructions composer flow.

## Integration with instruction deployment

Add optional source include:
- `tools/automations/ai_instructions_composer/cli.py` loads approved principle snippets.
- Deploy writes generated rules into `AGENTS.md`, `CLAUDE.md`, `GEMINI.md`.

Optional sync job extension:
- Extend `/Users/petrlavrov/calmmage/scripts/new_daily_jobs/ai_instructions_sync.py`
- Include principle bundle checksum in detailed payload.

## Acceptance criteria

- Principle can be captured in < 60s via CLI.
- Candidate skill can be generated from 1+ principles.
- Candidate can be tested and promoted to approved skill path.
- Approved principles can be deployed into instructions files.

## Implementation plan

Phase A:
- Build `tools/workflow/principles/cli.py` with capture/list/promote commands.
- Add storage helpers for markdown + Pydantic validation.

Phase B:
- Add `generate-skill` and `test-skill` commands.
- Add evaluator rubric for generated skill quality.

Phase C:
- Hook approved principles into AI instruction composer.
- Add daily summary of newly approved principles.

## Risks and mitigations

- Risk: noisy or overly broad principles.
  - Mitigation: enforce strict normalization and examples.
- Risk: rule duplication.
  - Mitigation: similarity check before approval.
- Risk: instruction bloat.
  - Mitigation: cap active principle bundle by priority and scope.

## Open questions

- Should principle approval require explicit human yes/no every time?
- Should skills live in repo or only in `$CODEX_HOME`?
- Should rejected principles be archived or deleted?
