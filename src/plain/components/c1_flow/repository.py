from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from plain.core.models import FlowError, ProjectFlow

try:
    import yaml
except ImportError as exc:  # pragma: no cover
    raise RuntimeError(
        "PyYAML is required for flow markdown persistence. Install with: uv add pyyaml"
    ) from exc


def slugify(text: str) -> str:
    slug = re.sub(r"[^a-zA-Z0-9]+", "-", text.strip().lower()).strip("-")
    return slug or "project"


class FlowRepository:
    """Markdown + YAML frontmatter persistence for project flows."""

    def __init__(self, base_dir: Path | str = Path("dev/notes/ecosystem/flows")):
        self.base_dir = Path(base_dir)

    def ensure_exists(self) -> None:
        self.base_dir.mkdir(parents=True, exist_ok=True)

    def project_path(self, slug: str) -> Path:
        return self.base_dir / f"{slug}.md"

    def load(self, identifier: str) -> ProjectFlow:
        self.ensure_exists()
        primary = self.project_path(slugify(identifier))
        if primary.exists():
            return self._load_file(primary)

        for path in sorted(self.base_dir.glob("*.md")):
            project = self._load_file(path)
            if project.project_name == identifier or project.project_id == identifier:
                return project

        raise FlowError(f"Project not found: {identifier}")

    def save(self, project: ProjectFlow, slug: str | None = None) -> Path:
        self.ensure_exists()
        resolved_slug = slug or slugify(project.project_name)
        path = self.project_path(resolved_slug)
        frontmatter = yaml.safe_dump(project.to_dict(), sort_keys=False, allow_unicode=False)
        body = render_project_body(project)
        content = f"---\n{frontmatter}---\n\n{body}\n"
        path.write_text(content)
        return path

    def list_project_slugs(self) -> list[str]:
        self.ensure_exists()
        return sorted(path.stem for path in self.base_dir.glob("*.md"))

    def _load_file(self, path: Path) -> ProjectFlow:
        text = path.read_text()
        payload, _ = split_frontmatter(text)
        if not payload:
            raise FlowError(f"Invalid flow file, missing YAML payload: {path}")
        return ProjectFlow.from_dict(payload)


def split_frontmatter(text: str) -> tuple[dict[str, Any], str]:
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

    yaml_part = "\n".join(lines[1:end_idx])
    body = "\n".join(lines[end_idx + 1 :])
    parsed = yaml.safe_load(yaml_part) or {}
    if not isinstance(parsed, dict):
        return {}, body
    return parsed, body


def render_project_body(project: ProjectFlow) -> str:
    rows: list[str] = []
    rows.append(f"# {project.project_name}")
    rows.append("")
    rows.append(f"- project_id: {project.project_id}")
    rows.append(f"- repository_path: {project.repository_path}")
    rows.append(f"- features: {len(project.features)}")
    rows.append(f"- updated_at: {project.updated_at.isoformat()}")
    rows.append("")
    rows.append("## Features")

    for feature in project.features:
        current = feature.get_phase_record(feature.current_phase)
        rows.append("")
        rows.append(f"### {feature.feature_id}")
        rows.append(f"- title: {feature.title}")
        rows.append(f"- vision: {feature.vision}")
        rows.append(f"- current_phase: {feature.current_phase.value}")
        rows.append(f"- phase_status: {current.status.value}")
        rows.append(f"- blockers: {len(current.blockers)}")
        if current.conversations:
            last = current.conversations[-1]
            rows.append(f"- last_conversation: {last.client}:{last.session_id}")
        else:
            rows.append("- last_conversation: none")

    return "\n".join(rows)
