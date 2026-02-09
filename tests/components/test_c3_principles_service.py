from pathlib import Path

import pytest

from plain.components.c3_principles.models import SkillTargetScope
from plain.components.c3_principles.repository import PrinciplesRepository
from plain.components.c3_principles.service import PrinciplesService

pytest.importorskip("yaml")


def _service(tmp_path: Path) -> PrinciplesService:
    repo = PrinciplesRepository(
        inbox_dir=tmp_path / "dev/notes/ecosystem/principles/inbox",
        approved_dir=tmp_path / "dev/notes/ecosystem/principles/approved",
        candidates_dir=tmp_path / "dev/notes/ecosystem/principles/candidates",
        skills_dir=tmp_path / "skills/local",
    )
    return PrinciplesService(repository=repo, workspace=tmp_path)


def test_capture_promote_and_skill_file_generation(tmp_path: Path) -> None:
    service = _service(tmp_path)

    note = service.capture(
        title="Keep docs concise",
        raw_quote="details in linked files, keep coordinator docs concise",
        source_path="/tmp/source.md",
        example_good="Use pointers to deep docs.",
        example_bad="Dump all details in one file.",
        tags=["workflow", "docs"],
    )

    candidate = service.promote(
        principle_id=note.principle_id,
        skill_name="concise-coordinator",
        target_scope=SkillTargetScope.CODING.value,
    )

    assert candidate.skill_path is not None
    skill_path = Path(candidate.skill_path)
    assert skill_path.exists()
    content = skill_path.read_text()
    assert "## Intent" in content
    assert "## Trigger Conditions" in content
    assert "## Step Protocol" in content
    assert "name: concise-coordinator" in content


def test_test_approve_and_deploy_flow(tmp_path: Path) -> None:
    service = _service(tmp_path)

    note = service.capture(
        title="Prefer clear command outputs",
        raw_quote="show exact command and expected output",
        source_path="/tmp/source.md",
        normalized_rule="Show exact command and expected output in demos.",
    )
    candidate = service.promote(
        principle_id=note.principle_id,
        skill_name="demo-clarity",
        target_scope=SkillTargetScope.RELEASE.value,
    )

    result = service.test_skill(candidate.candidate_id, prompt="Evaluate release demo quality")
    assert result.passed is True
    assert result.score >= 70

    approved = service.approve_skill(candidate.candidate_id)
    assert approved.status.value == "approved"

    deploy_result = service.deploy_approved_principles()
    assert deploy_result.bundle_path.exists()
    assert (tmp_path / "AGENTS.md").exists()
    assert (tmp_path / "CLAUDE.md").exists()
    assert (tmp_path / "GEMINI.md").exists()

    agents = (tmp_path / "AGENTS.md").read_text()
    assert "principles:begin" in agents
    assert "Show exact command and expected output in demos." in agents
