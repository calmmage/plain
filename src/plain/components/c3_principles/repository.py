from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from plain.components.c3_principles.models import (
    PrincipleNote,
    PrincipleStatus,
    SkillCandidate,
)
from plain.core.models import FlowError

try:
    import yaml
except ImportError:
    yaml = None


def slugify(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", text.lower().strip()).strip("-") or "skill"


class PrinciplesRepository:
    def __init__(
        self,
        inbox_dir: Path | str = Path("dev/notes/ecosystem/principles/inbox"),
        approved_dir: Path | str = Path("dev/notes/ecosystem/principles/approved"),
        candidates_dir: Path | str = Path("dev/notes/ecosystem/principles/candidates"),
        skills_dir: Path | str = Path("skills/local"),
    ):
        self.inbox_dir = Path(inbox_dir)
        self.approved_dir = Path(approved_dir)
        self.candidates_dir = Path(candidates_dir)
        self.skills_dir = Path(skills_dir)

    def ensure_dirs(self) -> None:
        self.inbox_dir.mkdir(parents=True, exist_ok=True)
        self.approved_dir.mkdir(parents=True, exist_ok=True)
        self.candidates_dir.mkdir(parents=True, exist_ok=True)
        self.skills_dir.mkdir(parents=True, exist_ok=True)

    def save_principle(self, note: PrincipleNote) -> Path:
        _require_yaml()
        note.validate()
        self.ensure_dirs()
        target_dir = self.approved_dir if note.status == PrincipleStatus.APPROVED else self.inbox_dir
        path = target_dir / f"{note.principle_id}.md"
        payload = yaml.safe_dump(note.to_dict(), sort_keys=False, allow_unicode=False)
        path.write_text(f"---\n{payload}---\n\n{render_principle_body(note)}\n")
        return path

    def load_principle(self, principle_id: str) -> PrincipleNote:
        self.ensure_dirs()
        for path in [self.inbox_dir / f"{principle_id}.md", self.approved_dir / f"{principle_id}.md"]:
            if path.exists():
                data, _ = split_frontmatter(path.read_text())
                return PrincipleNote.from_dict(data)
        raise FlowError(f"Principle not found: {principle_id}")

    def list_principles(self, status: str = "all") -> list[PrincipleNote]:
        self.ensure_dirs()
        status = status.lower().strip()
        notes: list[PrincipleNote] = []

        if status in ("all", PrincipleStatus.DRAFT.value):
            for path in sorted(self.inbox_dir.glob("*.md")):
                data, _ = split_frontmatter(path.read_text())
                notes.append(PrincipleNote.from_dict(data))

        if status in ("all", PrincipleStatus.APPROVED.value):
            for path in sorted(self.approved_dir.glob("*.md")):
                data, _ = split_frontmatter(path.read_text())
                notes.append(PrincipleNote.from_dict(data))

        return sorted(notes, key=lambda n: n.created_at)

    def move_principle_to_approved(self, principle_id: str) -> Path:
        note = self.load_principle(principle_id)
        note.status = PrincipleStatus.APPROVED

        inbox_path = self.inbox_dir / f"{principle_id}.md"
        if inbox_path.exists():
            inbox_path.unlink()

        return self.save_principle(note)

    def save_candidate(self, candidate: SkillCandidate) -> Path:
        _require_yaml()
        candidate.validate()
        self.ensure_dirs()
        path = self.candidates_dir / f"{candidate.candidate_id}.md"
        payload = yaml.safe_dump(candidate.to_dict(), sort_keys=False, allow_unicode=False)
        path.write_text(f"---\n{payload}---\n\n{render_candidate_body(candidate)}\n")
        return path

    def load_candidate(self, candidate_id: str) -> SkillCandidate:
        self.ensure_dirs()
        path = self.candidates_dir / f"{candidate_id}.md"
        if not path.exists():
            raise FlowError(f"Skill candidate not found: {candidate_id}")

        data, _ = split_frontmatter(path.read_text())
        return SkillCandidate.from_dict(data)

    def list_candidates(self, status: str = "all") -> list[SkillCandidate]:
        self.ensure_dirs()
        status = status.lower().strip()
        candidates: list[SkillCandidate] = []

        for path in sorted(self.candidates_dir.glob("*.md")):
            data, _ = split_frontmatter(path.read_text())
            candidate = SkillCandidate.from_dict(data)
            if status != "all" and candidate.status.value != status:
                continue
            candidates.append(candidate)

        return sorted(candidates, key=lambda c: c.created_at)

    def save_skill_markdown(self, skill_name: str, content: str) -> Path:
        self.ensure_dirs()
        slug = slugify(skill_name)
        skill_dir = self.skills_dir / slug
        skill_dir.mkdir(parents=True, exist_ok=True)
        path = skill_dir / "SKILL.md"
        path.write_text(content)
        return path


def split_frontmatter(text: str) -> tuple[dict[str, Any], str]:
    _require_yaml()
    if not text.startswith("---\n"):
        return {}, text

    lines = text.splitlines()
    end_idx = None
    for idx in range(1, len(lines)):
        if lines[idx].strip() == "---":
            end_idx = idx
            break

    if end_idx is None:
        return {}, text

    payload = yaml.safe_load("\n".join(lines[1:end_idx])) or {}
    body = "\n".join(lines[end_idx + 1 :])
    if not isinstance(payload, dict):
        return {}, body
    return payload, body


def render_principle_body(note: PrincipleNote) -> str:
    lines = [
        f"# {note.title}",
        "",
        f"raw_quote: \"{note.raw_quote}\"",
        "",
        "normalized_rule:",
        note.normalized_rule,
        "",
        "rationale:",
        note.rationale,
        "",
        "example_good:",
        note.example_good or "",
        "",
        "example_bad:",
        note.example_bad or "",
    ]
    return "\n".join(lines).rstrip()


def render_candidate_body(candidate: SkillCandidate) -> str:
    lines = [
        f"# {candidate.name}",
        "",
        f"status: {candidate.status.value}",
        f"scope: {candidate.target_scope.value}",
        f"principles: {', '.join(candidate.principle_ids)}",
    ]
    if candidate.skill_path:
        lines.append(f"skill_path: {candidate.skill_path}")
    if candidate.last_test_score is not None:
        lines.append(f"last_test_score: {candidate.last_test_score}")
    if candidate.last_test_notes:
        lines.append(f"last_test_notes: {candidate.last_test_notes}")
    return "\n".join(lines)


def _require_yaml() -> None:
    if yaml is None:
        raise FlowError("PyYAML is required for principle storage. Install with: uv add pyyaml")
