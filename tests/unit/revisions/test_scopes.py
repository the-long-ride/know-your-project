from datetime import UTC, datetime

from know_your_project.domain.artifacts import FactCandidate, Provenance
from know_your_project.domain.ids import ArtifactId, ProjectId
from know_your_project.revisions.engine import RevisionEngine


def test_fact_version_keeps_revision_scope() -> None:
    plan = RevisionEngine().plan(
        project_id=ProjectId("p"),
        artifact_id=ArtifactId("a"),
        previous=[],
        current=[FactCandidate(
            subject="A", predicate="behavior", value="B", confidence=1.0,
            provenance=Provenance(source_kind="git", source_id="a"),
        )],
        effective_at=datetime(2026, 9, 1, tzinfo=UTC),
        scope="branch:refs/heads/main",
    )
    assert plan.active_versions[0].scope == "branch:refs/heads/main"
