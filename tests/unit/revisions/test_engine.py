from datetime import UTC, datetime

from know_your_project.domain.artifacts import FactCandidate, Provenance
from know_your_project.domain.ids import ArtifactId, ProjectId
from know_your_project.revisions.engine import RevisionEngine


def fact(value: str) -> FactCandidate:
    return FactCandidate(
        subject="PaymentRetry",
        predicate="max_attempts",
        value=value,
        confidence=1.0,
        provenance=Provenance(source_kind="git", source_id="payment.cs"),
    )


def test_changed_fact_invalidates_only_same_artifact_subject_predicate() -> None:
    engine = RevisionEngine()
    at1 = datetime(2026, 9, 1, tzinfo=UTC)
    at2 = datetime(2026, 9, 2, tzinfo=UTC)
    first = engine.plan(
        project_id=ProjectId("p"),
        artifact_id=ArtifactId("git:r:/Payment.cs"),
        previous=[],
        current=[fact("3")],
        effective_at=at1,
    )
    second = engine.plan(
        project_id=ProjectId("p"),
        artifact_id=ArtifactId("git:r:/Payment.cs"),
        previous=first.active_versions,
        current=[fact("5")],
        effective_at=at2,
    )
    assert [m.kind for m in second.mutations] == ["invalidate", "upsert"]
    assert second.active_versions[0].value == "5"


def test_unchanged_fact_keeps_existing_version_without_mutation() -> None:
    engine = RevisionEngine()
    at1 = datetime(2026, 9, 1, tzinfo=UTC)
    at2 = datetime(2026, 9, 2, tzinfo=UTC)
    first = engine.plan(
        project_id=ProjectId("p"), artifact_id=ArtifactId("a"), previous=[],
        current=[fact("3")], effective_at=at1,
    )
    second = engine.plan(
        project_id=ProjectId("p"), artifact_id=ArtifactId("a"),
        previous=first.active_versions, current=[fact("3")], effective_at=at2,
    )
    assert second.mutations == []
    assert second.active_versions[0].edge_uuid == first.active_versions[0].edge_uuid


def test_removed_fact_is_invalidated_and_no_longer_active() -> None:
    engine = RevisionEngine()
    at1 = datetime(2026, 9, 1, tzinfo=UTC)
    at2 = datetime(2026, 9, 2, tzinfo=UTC)
    first = engine.plan(
        project_id=ProjectId("p"), artifact_id=ArtifactId("a"), previous=[],
        current=[fact("3")], effective_at=at1,
    )
    second = engine.plan(
        project_id=ProjectId("p"), artifact_id=ArtifactId("a"),
        previous=first.active_versions, current=[], effective_at=at2,
    )
    assert [m.kind for m in second.mutations] == ["invalidate"]
    assert second.active_versions == []
