from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

from plain.components.c3_principles.models import (
    PrincipleNote,
    PrincipleStatus,
    SkillCandidate,
    SkillCandidateStatus,
    SkillTargetScope,
    SkillTestResult,
    utc_now,
)
from plain.components.c3_principles.repository import PrinciplesRepository, slugify
from plain.core.models import FlowError

BEGIN_MARKER = "<!-- principles:begin -->"
END_MARKER = "<!-- principles:end -->"


@dataclass(slots=True)
class DeployResult:
    modified_files: list[Path]
    bundle_path: Path


@dataclass(slots=True)
class PrinciplesService:
    repository: PrinciplesRepository
    workspace: Path = Path(".")

    @classmethod
    def create_default(cls) -> "PrinciplesService":
        return cls(repository=PrinciplesRepository())

    def capture(
        self,
        title: str,
        raw_quote: str,
        source_path: str,
        normalized_rule: str | None = None,
        rationale: str | None = None,
        example_good: str | None = None,
        example_bad: str | None = None,
        tags: Iterable[str] | None = None,
        source_session_id: str | None = None,
    ) -> PrincipleNote:
        now = utc_now()
        note = PrincipleNote(
            principle_id=self._next_principle_id(now),
            title=title.strip(),
            raw_quote=raw_quote.strip(),
            normalized_rule=(normalized_rule or self._normalize_rule(raw_quote)).strip(),
            rationale=(rationale or "Captured from active work session.").strip(),
            source_path=source_path.strip(),
            source_session_id=source_session_id,
            tags=[tag.strip() for tag in (tags or []) if tag.strip()],
            example_good=(example_good or None),
            example_bad=(example_bad or None),
            status=PrincipleStatus.DRAFT,
            created_at=now,
            updated_at=now,
        )
        self.repository.save_principle(note)
        return note

    def list_principles(self, status: str = "all") -> list[PrincipleNote]:
        return self.repository.list_principles(status=status)

    def list_candidates(self, status: str = "all") -> list[SkillCandidate]:
        return self.repository.list_candidates(status=status)

    def promote(
        self,
        principle_id: str,
        skill_name: str,
        target_scope: str = SkillTargetScope.CODING.value,
        include_principle_ids: Iterable[str] | None = None,
    ) -> SkillCandidate:
        now = utc_now()
        try:
            scope = SkillTargetScope(target_scope)
        except ValueError as exc:
            raise FlowError(f"Invalid target scope: {target_scope}") from exc

        principle_ids = [principle_id] + [item for item in (include_principle_ids or []) if item]
        principle_ids = _dedupe(principle_ids)

        principles = [self.repository.load_principle(item) for item in principle_ids]
        skill_content = build_skill_markdown(skill_name, principles, scope)
        skill_path = self.repository.save_skill_markdown(skill_name, skill_content)

        candidate = SkillCandidate(
            candidate_id=self._next_candidate_id(now),
            name=skill_name,
            principle_ids=[item.principle_id for item in principles],
            target_scope=scope,
            status=SkillCandidateStatus.DRAFT,
            skill_path=str(skill_path),
            created_at=now,
            updated_at=now,
        )
        self.repository.save_candidate(candidate)
        return candidate

    def test_skill(self, candidate_id: str, prompt: str) -> SkillTestResult:
        candidate = self.repository.load_candidate(candidate_id)
        if not candidate.skill_path:
            raise FlowError(f"Candidate has no generated skill path: {candidate_id}")

        skill_path = self._resolve(candidate.skill_path)
        if not skill_path.exists():
            raise FlowError(f"Generated skill file missing: {skill_path}")

        content = skill_path.read_text()
        score = 100
        notes: list[str] = []

        required_sections = [
            "## Intent",
            "## Trigger Conditions",
            "## Step Protocol",
            "## Output Contract",
            "## Anti-patterns",
            "## Examples",
        ]
        for section in required_sections:
            if section not in content:
                score -= 15
                notes.append(f"missing section: {section}")

        prompt_text = prompt.strip()
        if len(prompt_text) < 10:
            score -= 5
            notes.append("test prompt is too short for realistic validation")

        for principle_id in candidate.principle_ids:
            principle = self.repository.load_principle(principle_id)
            snippet = principle.normalized_rule[:24].lower()
            if snippet and snippet not in content.lower():
                score -= 5
                notes.append(f"principle rule not reflected clearly: {principle_id}")

        score = max(0, min(100, score))
        passed = score >= 70

        candidate.test_prompt = prompt_text
        candidate.last_test_score = score
        candidate.last_test_notes = "; ".join(notes) if notes else "pass"
        candidate.status = SkillCandidateStatus.REVIEW if passed else SkillCandidateStatus.DRAFT
        candidate.updated_at = utc_now()
        self.repository.save_candidate(candidate)

        return SkillTestResult(
            candidate_id=candidate.candidate_id,
            score=score,
            notes=notes or ["pass"],
            passed=passed,
        )

    def approve_skill(self, candidate_id: str) -> SkillCandidate:
        candidate = self.repository.load_candidate(candidate_id)
        if candidate.last_test_score is None:
            raise FlowError("Cannot approve skill before test-skill execution")
        if candidate.last_test_score < 70:
            raise FlowError(
                f"Cannot approve skill with failing score {candidate.last_test_score} (< 70)"
            )

        candidate.status = SkillCandidateStatus.APPROVED
        candidate.updated_at = utc_now()
        self.repository.save_candidate(candidate)

        for principle_id in candidate.principle_ids:
            note = self.repository.load_principle(principle_id)
            note.status = PrincipleStatus.APPROVED
            note.updated_at = utc_now()
            self.repository.move_principle_to_approved(principle_id)
            self.repository.save_principle(note)

        return candidate

    def deploy_approved_principles(
        self,
        targets: Iterable[str] | None = None,
    ) -> DeployResult:
        approved = self.repository.list_principles(status=PrincipleStatus.APPROVED.value)
        if not approved:
            raise FlowError("No approved principles found to deploy")

        bundle = render_principles_bundle(approved)
        bundle_path = self._resolve("dev/notes/ecosystem/principles/approved/bundle.md")
        bundle_path.parent.mkdir(parents=True, exist_ok=True)
        bundle_path.write_text(bundle)

        target_paths = [
            self._resolve(path)
            for path in (targets or ["AGENTS.md", "CLAUDE.md", "GEMINI.md"])
        ]

        modified: list[Path] = []
        for path in target_paths:
            original = path.read_text() if path.exists() else ""
            updated = upsert_principles_block(original, bundle)
            if updated != original:
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text(updated)
                modified.append(path)

        return DeployResult(modified_files=modified, bundle_path=bundle_path)

    def _next_principle_id(self, now) -> str:
        date_prefix = now.strftime("pr_%Y_%m_%d")
        highest = 0
        regex = re.compile(rf"^{re.escape(date_prefix)}_(\\d+)$")

        for note in self.repository.list_principles(status="all"):
            match = regex.match(note.principle_id)
            if match:
                highest = max(highest, int(match.group(1)))

        return f"{date_prefix}_{highest + 1:02d}"

    def _next_candidate_id(self, now) -> str:
        date_prefix = now.strftime("cand_%Y_%m_%d")
        highest = 0
        regex = re.compile(rf"^{re.escape(date_prefix)}_(\\d+)$")

        for candidate in self.repository.list_candidates(status="all"):
            match = regex.match(candidate.candidate_id)
            if match:
                highest = max(highest, int(match.group(1)))

        return f"{date_prefix}_{highest + 1:02d}"

    def _normalize_rule(self, raw_quote: str) -> str:
        cleaned = " ".join(raw_quote.strip().split())
        if not cleaned:
            return "Define one actionable rule from the captured quote."
        first_sentence = re.split(r"(?<=[.!?])\\s+", cleaned)[0]
        return first_sentence[:220].rstrip()

    def _resolve(self, path: str | Path) -> Path:
        candidate = Path(path)
        if candidate.is_absolute():
            return candidate
        return self.workspace / candidate


def build_skill_markdown(
    name: str,
    principles: list[PrincipleNote],
    target_scope: SkillTargetScope,
) -> str:
    normalized_name = slugify(name)
    protocol_lines = [f"1. Apply rule: {item.normalized_rule}" for item in principles]

    anti_patterns: list[str] = []
    good_examples: list[str] = []
    bad_examples: list[str] = []
    for item in principles:
        if item.example_bad:
            anti_patterns.append(item.example_bad)
        if item.example_good:
            good_examples.append(item.example_good)
        elif item.example_bad:
            bad_examples.append(item.example_bad)

    if not anti_patterns:
        anti_patterns = ["Do not produce verbose answers when concise action is possible."]

    lines = [
        "---",
        f"name: {normalized_name}",
        f"description: Generated principle skill for {target_scope.value} workflows.",
        "---",
        "",
        f"# {name}",
        "",
        "## Intent",
        f"Apply validated human guidance patterns for {target_scope.value} tasks.",
        "",
        "## Trigger Conditions",
        f"Use when work scope matches `{target_scope.value}` and related principles.",
        "",
        "## Step Protocol",
        *protocol_lines,
        "",
        "## Output Contract",
        "- Output remains concise and actionable.",
        "- Include clear file paths or commands when implementation is required.",
        "- Mention validation checks or risks explicitly.",
        "",
        "## Anti-patterns",
        *[f"- {item}" for item in anti_patterns],
        "",
        "## Examples",
        "### Good",
    ]

    if good_examples:
        lines.extend([f"- {item}" for item in good_examples])
    else:
        lines.append("- Uses pointer-only context with concrete action steps.")

    lines.extend(["", "### Bad"])
    if bad_examples:
        lines.extend([f"- {item}" for item in bad_examples])
    else:
        lines.append("- Dumps long unstructured guidance without actionable steps.")

    return "\n".join(lines).rstrip() + "\n"


def render_principles_bundle(notes: list[PrincipleNote]) -> str:
    lines = [
        "# Approved Principles Bundle",
        "",
        "Generated from c3 principles workflow.",
        "",
    ]
    for note in notes:
        lines.extend(
            [
                f"## {note.principle_id} - {note.title}",
                f"- rule: {note.normalized_rule}",
                f"- rationale: {note.rationale}",
                f"- source: {note.source_path}",
                "",
            ]
        )
    return "\n".join(lines).rstrip() + "\n"


def upsert_principles_block(original: str, bundle: str) -> str:
    block = f"{BEGIN_MARKER}\n{bundle.rstrip()}\n{END_MARKER}"

    if BEGIN_MARKER in original and END_MARKER in original:
        pattern = re.compile(
            rf"{re.escape(BEGIN_MARKER)}.*?{re.escape(END_MARKER)}",
            flags=re.DOTALL,
        )
        return pattern.sub(block, original).rstrip() + "\n"

    base = original.rstrip()
    if base:
        return base + "\n\n" + block + "\n"
    return block + "\n"


def _dedupe(values: Iterable[str]) -> list[str]:
    seen: set[str] = set()
    output: list[str] = []
    for value in values:
        if value not in seen:
            output.append(value)
            seen.add(value)
    return output
