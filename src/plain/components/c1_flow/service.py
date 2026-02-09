from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

from plain.components.c1_flow.repository import FlowRepository, slugify
from plain.core.models import (
    ArtifactRef,
    ConversationRef,
    FeatureFlow,
    FlowError,
    Phase,
    ProjectFlow,
    utc_now,
)
from plain.core.state_machine import advance_phase, can_advance, start_phase


CLIENT_TO_CLI = {
    "claude": "claude",
    "codex": "codex",
    "gemini": "gemini",
}


@dataclass(slots=True)
class FlowService:
    repository: FlowRepository

    @classmethod
    def create_default(cls) -> "FlowService":
        return cls(repository=FlowRepository())

    def init_project(
        self,
        project_name: str,
        repository_path: str,
        tags: Iterable[str] | None = None,
    ) -> ProjectFlow:
        now = utc_now()
        slug = slugify(project_name)
        project = ProjectFlow(
            project_id=f"prj_{slug.replace('-', '_')}",
            project_name=project_name,
            repository_path=repository_path,
            tags=list(tags or []),
            created_at=now,
            updated_at=now,
        )
        self.repository.save(project, slug=slug)
        return project

    def load_project(self, identifier: str) -> ProjectFlow:
        return self.repository.load(identifier)

    def add_feature(
        self,
        project_identifier: str,
        title: str,
        vision: str,
        feature_id: str | None = None,
    ) -> FeatureFlow:
        project = self.load_project(project_identifier)
        generated = feature_id or self._generate_feature_id(project, title)
        if any(item.feature_id == generated for item in project.features):
            raise FlowError(f"Feature already exists: {generated}")

        feature = FeatureFlow.create(feature_id=generated, title=title, vision=vision)
        project.features.append(feature)
        project.updated_at = utc_now()
        self.repository.save(project)
        return feature

    def get_feature(self, project_identifier: str, feature_id: str) -> FeatureFlow:
        project = self.load_project(project_identifier)
        return project.get_feature(feature_id)

    def phase_start(self, project_identifier: str, feature_id: str, phase: str) -> FeatureFlow:
        project = self.load_project(project_identifier)
        feature = project.get_feature(feature_id)
        start_phase(feature, Phase(phase))
        project.updated_at = utc_now()
        self.repository.save(project)
        return feature

    def phase_advance(self, project_identifier: str, feature_id: str) -> FeatureFlow:
        project = self.load_project(project_identifier)
        feature = project.get_feature(feature_id)
        advance_phase(feature)
        project.updated_at = utc_now()
        self.repository.save(project)
        return feature

    def add_feedback(self, project_identifier: str, feature_id: str, text: str) -> FeatureFlow:
        project = self.load_project(project_identifier)
        feature = project.get_feature(feature_id)
        phase_record = feature.get_phase_record()
        phase_record.feedback.append(text.strip())
        feature.updated_at = utc_now()
        project.updated_at = feature.updated_at
        self.repository.save(project)
        return feature

    def link_conversation(
        self,
        project_identifier: str,
        feature_id: str,
        client: str,
        session_id: str,
        cwd: str,
        summary: str | None = None,
        phase: str | None = None,
    ) -> ConversationRef:
        project = self.load_project(project_identifier)
        feature = project.get_feature(feature_id)
        target_phase = Phase(phase) if phase else feature.current_phase
        phase_record = feature.get_phase_record(target_phase)
        conversation = ConversationRef(
            client=client,
            session_id=session_id,
            cwd=cwd,
            summary=summary,
        )
        phase_record.conversations.append(conversation)
        feature.updated_at = utc_now()
        project.updated_at = feature.updated_at
        self.repository.save(project)
        return conversation

    def add_artifact(
        self,
        project_identifier: str,
        feature_id: str,
        kind: str,
        path: str,
        note: str | None = None,
        phase: str | None = None,
    ) -> ArtifactRef:
        project = self.load_project(project_identifier)
        feature = project.get_feature(feature_id)
        target_phase = Phase(phase) if phase else feature.current_phase
        phase_record = feature.get_phase_record(target_phase)
        artifact = ArtifactRef(kind=kind, path=path, note=note)
        phase_record.artifacts.append(artifact)
        feature.updated_at = utc_now()
        project.updated_at = feature.updated_at
        self.repository.save(project)
        return artifact

    def add_phase_metadata(
        self,
        project_identifier: str,
        feature_id: str,
        code_link: str | None = None,
        entry_point: str | None = None,
        explanation: str | None = None,
        phase: str | None = None,
    ) -> FeatureFlow:
        project = self.load_project(project_identifier)
        feature = project.get_feature(feature_id)
        target_phase = Phase(phase) if phase else feature.current_phase
        phase_record = feature.get_phase_record(target_phase)

        if code_link:
            phase_record.code_links.append(code_link)
        if entry_point:
            phase_record.entry_points.append(entry_point)
        if explanation:
            phase_record.explanations.append(explanation)

        feature.updated_at = utc_now()
        project.updated_at = feature.updated_at
        self.repository.save(project)
        return feature

    def board_rows(self, project_identifier: str) -> list[dict[str, str]]:
        project = self.load_project(project_identifier)
        rows: list[dict[str, str]] = []
        for feature in project.features:
            phase_record = feature.get_phase_record(feature.current_phase)
            last_conversation = "-"
            if phase_record.conversations:
                conversation = phase_record.conversations[-1]
                last_conversation = f"{conversation.client}:{conversation.session_id}"

            rows.append(
                {
                    "Feature": feature.feature_id,
                    "Current phase": feature.current_phase.value,
                    "Phase status": phase_record.status.value,
                    "Last update": feature.updated_at.isoformat(),
                    "Open blockers": str(len(phase_record.blockers)),
                    "Last conversation": last_conversation,
                }
            )
        return rows

    def snapshot(self, project_identifier: str) -> str:
        project = self.load_project(project_identifier)
        lines: list[str] = []
        lines.append(f"project={project.project_name} ({project.project_id})")
        lines.append(f"repo={project.repository_path}")
        lines.append(f"features={len(project.features)}")
        lines.append("")
        for feature in project.features:
            phase = feature.current_phase.value
            record = feature.get_phase_record(feature.current_phase)
            advance_ok, advance_reason = can_advance(feature)
            lines.append(f"- {feature.feature_id}: {phase}/{record.status.value}")
            lines.append(f"  title: {feature.title}")
            lines.append(f"  blockers: {len(record.blockers)}")
            lines.append(
                f"  advance: {'yes' if advance_ok else 'no'} ({advance_reason})"
            )
        return "\n".join(lines)

    def resume_command(
        self,
        project_identifier: str,
        feature_id: str,
        phase: str | None = None,
    ) -> str:
        project = self.load_project(project_identifier)
        feature = project.get_feature(feature_id)
        target_phase = Phase(phase) if phase else feature.current_phase
        phase_record = feature.get_phase_record(target_phase)

        if not phase_record.conversations:
            raise FlowError(
                f"No conversations linked for {feature.feature_id} in {target_phase.value}"
            )

        conversation = phase_record.conversations[-1]
        client_cli = CLIENT_TO_CLI.get(conversation.client, conversation.client)
        return f"cd {conversation.cwd} && {client_cli} --resume {conversation.session_id}"

    def _generate_feature_id(self, project: ProjectFlow, title: str) -> str:
        base = slugify(title).replace("-", "_")
        candidate = f"feat_{base}"
        idx = 2
        existing = {feature.feature_id for feature in project.features}
        while candidate in existing:
            candidate = f"feat_{base}_{idx}"
            idx += 1
        return candidate
