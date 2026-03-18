# PRD 5: Obsidian ideas ingestion, backlinks, structured store

Source: `/Users/petrlavrov/calmmage/obsidian/Inbox/Human-driven AI projects.md`

Raw source excerpt (verbatim):

-> Obsidian / local daily notes with ideas and visions
-> automated daily jobs taht parses (hybrid: structured and ai) the ideas and exports them to our db / storage
-> preserve backlinks to easily jump to source page and verify correctness of extraction
-> in our app: structured clean data model - projects + features
Also would be nice to have “ideas”, experiments, preproject
- always store a backlink to original obsidian note.

Reference: my obsidian vault, specifically, daily notes, preprojects, workalongs and thought dumps.

## Goal

Build a reliable ingestion pipeline that extracts project/feature signals from Obsidian notes while preserving traceability to source notes.

## Existing references

- `/Users/petrlavrov/calmmage/obsidian/daily/`
- `/Users/petrlavrov/calmmage/obsidian/preproject/`
- `/Users/petrlavrov/calmmage/obsidian/workalongs/`
- `/Users/petrlavrov/calmmage/obsidian/dumps/`
- `/Users/petrlavrov/calmmage/tools/automations/obsidian_sorter/src/obsidian_sorter.py`
- `/Users/petrlavrov/calmmage/calmlib/obsidian/obsidian_db.py`

## Scope

In scope:
- Daily incremental note scan.
- Hybrid extraction (structured fields + AI parser).
- Entity model: project, feature, idea, experiment, preproject.
- Backlink preservation for every extracted item.
- Change history for extracted items.

Out of scope:
- Perfect NLP extraction from all note styles in v1.

## Data model

```python
from datetime import datetime
from pydantic import BaseModel, Field


class SourceRef(BaseModel):
    note_path: str
    note_title: str
    heading: str | None = None
    block_id: str | None = None
    excerpt: str | None = None
    captured_at: datetime


class ItemKind(str, Enum):
    IDEA = "idea"
    EXPERIMENT = "experiment"
    PREPROJECT = "preproject"
    PROJECT = "project"
    FEATURE = "feature"


class IngestedItem(BaseModel):
    item_id: str
    kind: ItemKind
    title: str
    description: str
    project_id: str | None = None
    feature_id: str | None = None
    confidence: float = 0.0
    tags: list[str] = Field(default_factory=list)
    source_refs: list[SourceRef] = Field(default_factory=list)
    created_at: datetime
    updated_at: datetime
```

## Classification rules

Base folders -> default type:
- `daily/` -> `idea`
- `dumps/` -> `idea`
- `workalongs/` -> `experiment`
- `preproject/` -> `preproject`

AI can override type if confidence is high and evidence is explicit.

## Pipeline design

1. Discover changed notes since last run.
2. Parse frontmatter/headers/checklists/inline metadata.
3. Extract candidate items (structured).
4. Run AI normalization for ambiguous blocks.
5. Resolve duplicates/links to existing project/feature entities.
6. Persist entities with `source_refs` backlinks.
7. Emit review report for low-confidence items.

## Incremental sync state

Keep cursor in:
- `/Users/petrlavrov/calmmage/dev/notes/ecosystem/state/obsidian_ingest_state.json`

State fields:
- last scan time
- file hash index
- last successful run id

## Duplicate and merge logic

Signals:
- title similarity
- overlapping keywords
- same project links
- same source note path

Merge policy:
- auto-merge only above strict threshold.
- otherwise create review candidate and keep both.

## Backlink policy

Every ingested item must include at least one source pointer:
- exact note path
- optional heading/block reference
- raw excerpt for verification

Output examples:

```markdown
- item_id: itm_20260209_0031
- kind: feature
- title: "Review queue table"
- source:
  - /Users/petrlavrov/calmmage/obsidian/workalongs/Workalong - 6 Feb 2026.md#Review ideas
```

## Job contract

Job name suggestion: `obsidian_idea_ingest`

`JobResult.detailed` should include:
- notes scanned
- items created
- items updated
- low-confidence items
- duplicate candidates

## API surface for downstream tools

Read APIs:
- `get_items(kind=None, project_id=None, min_confidence=0.0)`
- `get_item_with_sources(item_id)`
- `get_pending_review_items()`

Write APIs:
- `approve_item(item_id)`
- `merge_items(primary_id, duplicate_id)`
- `reclassify_item(item_id, kind)`

## Acceptance criteria

- Scans changed notes in target folders daily.
- Stores extracted entities with explicit source backlinks.
- Supports 5 target kinds: idea/experiment/preproject/project/feature.
- Produces review queue for uncertain extraction.
- Maintains incremental cursor and avoids full reprocessing by default.

## Implementation plan

Phase A:
- Folder scanner + structured parser + cursor tracking.
- Basic entity persistence and backlink recording.

Phase B:
- AI normalization and classification.
- Duplicate detection and merge suggestions.

Phase C:
- Downstream query API for review UI and daily automation.
- Quality dashboard metrics.

## Risks and mitigations

- Risk: extraction quality variability across note styles.
  - Mitigation: confidence thresholds + review queue.
- Risk: backlinks become stale after note moves.
  - Mitigation: store `calmmage_id` or stable IDs where available.
- Risk: over-creation of noisy items.
  - Mitigation: stricter item creation rules for low-confidence text.

## Open questions

- Should source excerpt be mandatory for every item?
- Do we keep full historical versions or only latest + audit log?
- Which UI should own the low-confidence review queue first (CLI or web)?
