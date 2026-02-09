from plain.core.models import ArtifactRef, FeatureFlow, Phase, PhaseStatus
from plain.core.state_machine import advance_phase, can_advance


def test_make_it_work_requires_demo_and_entrypoint() -> None:
    feature = FeatureFlow.create("feat_demo", "Demo", "Build demo flow")

    ok, reason = can_advance(feature)
    assert not ok
    assert "entry" in reason

    phase = feature.get_phase_record(Phase.MAKE_IT_WORK)
    phase.artifacts.append(ArtifactRef(kind="demo", path="dev/notes/demos/c1.md"))
    phase.entry_points.append("make demo-c1")

    ok, _ = can_advance(feature)
    assert ok


def test_advance_moves_make_it_work_to_test() -> None:
    feature = FeatureFlow.create("feat_demo", "Demo", "Build demo flow")
    phase = feature.get_phase_record(Phase.MAKE_IT_WORK)
    phase.status = PhaseStatus.ACTIVE
    phase.artifacts.append(ArtifactRef(kind="demo", path="dev/notes/demos/c1.md"))
    phase.entry_points.append("make demo-c1")

    advance_phase(feature)

    assert feature.current_phase == Phase.TEST
    assert feature.get_phase_record(Phase.MAKE_IT_WORK).status == PhaseStatus.DONE
    assert feature.get_phase_record(Phase.TEST).status == PhaseStatus.ACTIVE


def test_test_phase_requires_feedback() -> None:
    feature = FeatureFlow.create("feat_demo", "Demo", "Build demo flow")
    make_phase = feature.get_phase_record(Phase.MAKE_IT_WORK)
    make_phase.artifacts.append(ArtifactRef(kind="demo", path="dev/notes/demos/c1.md"))
    make_phase.entry_points.append("make demo-c1")
    advance_phase(feature)

    ok, reason = can_advance(feature)
    assert not ok
    assert "feedback" in reason

    test_phase = feature.get_phase_record(Phase.TEST)
    test_phase.feedback.append("First human feedback cycle complete")

    ok, _ = can_advance(feature)
    assert ok


def test_polish_requires_readme_and_deploy_note() -> None:
    feature = FeatureFlow.create("feat_demo", "Demo", "Build demo flow")
    make_phase = feature.get_phase_record(Phase.MAKE_IT_WORK)
    make_phase.artifacts.append(ArtifactRef(kind="demo", path="dev/notes/demos/c1.md"))
    make_phase.entry_points.append("make demo-c1")
    advance_phase(feature)

    test_phase = feature.get_phase_record(Phase.TEST)
    test_phase.feedback.append("Looks good")
    advance_phase(feature)

    polish_phase = feature.get_phase_record(Phase.POLISH)
    polish_phase.artifacts.append(ArtifactRef(kind="readme", path="README.md"))

    ok, _ = can_advance(feature)
    assert not ok

    polish_phase.artifacts.append(
        ArtifactRef(kind="deploy_note", path="dev/notes/deploy/c1.md")
    )

    ok, _ = can_advance(feature)
    assert ok

    advance_phase(feature)
    assert feature.completed_at is not None
