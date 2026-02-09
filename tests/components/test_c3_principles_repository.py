from pathlib import Path

import pytest

from plain.components.c3_principles.models import PrincipleNote
from plain.components.c3_principles.repository import PrinciplesRepository, split_frontmatter

pytest.importorskip("yaml")


def test_load_fixture_frontmatter() -> None:
    payload, _ = split_frontmatter(Path("tests/fixtures/c3/sample_principle.md").read_text())
    note = PrincipleNote.from_dict(payload)

    assert note.principle_id == "pr_2026_02_09_01"
    assert note.title == "Keep coordinator docs pointer-only"
    assert note.status.value == "draft"


def test_repository_save_and_load_candidate_like_principle(tmp_path: Path) -> None:
    repo = PrinciplesRepository(
        inbox_dir=tmp_path / "inbox",
        approved_dir=tmp_path / "approved",
        candidates_dir=tmp_path / "candidates",
        skills_dir=tmp_path / "skills",
    )

    payload, _ = split_frontmatter(Path("tests/fixtures/c3/sample_principle.md").read_text())
    note = PrincipleNote.from_dict(payload)
    repo.save_principle(note)

    loaded = repo.load_principle(note.principle_id)
    assert loaded.normalized_rule.startswith("Keep coordinator docs pointer-only")
