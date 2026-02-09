from __future__ import annotations

from plain.core.models import (
    PHASE_ORDER,
    FeatureFlow,
    FlowError,
    Phase,
    PhaseStatus,
    utc_now,
)


def next_phase(phase: Phase) -> Phase | None:
    idx = PHASE_ORDER.index(phase)
    if idx >= len(PHASE_ORDER) - 1:
        return None
    return PHASE_ORDER[idx + 1]


def can_advance(feature: FeatureFlow) -> tuple[bool, str]:
    phase = feature.current_phase
    record = feature.get_phase_record(phase)

    if phase == Phase.MAKE_IT_WORK:
        has_demo = any(artifact.kind == "demo" for artifact in record.artifacts)
        has_entry_note = any(
            "entry" in (artifact.note or "").lower() for artifact in record.artifacts
        )
        has_entry_point = len(record.entry_points) > 0
        ok = has_demo and (has_entry_note or has_entry_point)
        return ok, "need demo artifact and entry instructions"

    if phase == Phase.TEST:
        has_feedback = len(record.feedback) > 0
        return has_feedback, "need at least one feedback cycle"

    if phase == Phase.POLISH:
        kinds = {artifact.kind for artifact in record.artifacts}
        required = {"readme", "deploy_note"}
        ok = required.issubset(kinds)
        return ok, "need readme + deploy_note"

    return False, "invalid phase"


def start_phase(feature: FeatureFlow, phase: Phase) -> None:
    now = utc_now()
    current = feature.current_phase
    current_idx = PHASE_ORDER.index(current)
    target_idx = PHASE_ORDER.index(phase)

    if target_idx > current_idx + 1:
        raise FlowError("Cannot skip forward more than one phase")

    if target_idx < current_idx - 1:
        raise FlowError("Rollback is limited to one phase")

    if target_idx == current_idx + 1:
        ok, reason = can_advance(feature)
        if not ok:
            raise FlowError(f"Cannot move to next phase: {reason}")
        current_record = feature.get_phase_record(current)
        current_record.status = PhaseStatus.DONE
        current_record.finished_at = now

    if target_idx == current_idx - 1:
        previous_record = feature.get_phase_record(phase)
        previous_record.finished_at = None

    feature.current_phase = phase
    target_record = feature.get_phase_record(phase)
    target_record.status = PhaseStatus.ACTIVE
    target_record.started_at = target_record.started_at or now
    feature.updated_at = now


def advance_phase(feature: FeatureFlow) -> None:
    now = utc_now()
    ok, reason = can_advance(feature)
    if not ok:
        raise FlowError(f"Cannot advance phase: {reason}")

    current = feature.current_phase
    record = feature.get_phase_record(current)
    record.status = PhaseStatus.DONE
    record.finished_at = now

    nxt = next_phase(current)
    if nxt is None:
        feature.completed_at = now
        feature.updated_at = now
        return

    feature.current_phase = nxt
    nxt_record = feature.get_phase_record(nxt)
    nxt_record.status = PhaseStatus.ACTIVE
    nxt_record.started_at = nxt_record.started_at or now
    feature.updated_at = now


def block_phase(feature: FeatureFlow, note: str) -> None:
    record = feature.get_phase_record(feature.current_phase)
    record.status = PhaseStatus.BLOCKED
    if note:
        record.blockers.append(note)
    feature.updated_at = utc_now()
