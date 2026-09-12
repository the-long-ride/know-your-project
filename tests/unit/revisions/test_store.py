from datetime import UTC, datetime

from know_your_project.domain.ids import ArtifactId, ProjectId, ReleaseId
from know_your_project.revisions.models import Release
from know_your_project.revisions.store import SqliteRevisionStore


async def test_release_round_trip(tmp_path) -> None:
    store = SqliteRevisionStore(str(tmp_path / "state.db"))
    await store.initialize()
    release = Release(
        project_id=ProjectId("p"), release_id=ReleaseId("v1"), tag="v1",
        commit_sha="a" * 40, effective_at=datetime(2026, 9, 1, tzinfo=UTC),
    )
    await store.save_release(release)
    loaded = await store.get_release(ProjectId("p"), ReleaseId("v1"))
    assert loaded is not None
    assert loaded.commit_sha == "a" * 40
    assert await store.get_active_facts(ProjectId("p"), ArtifactId("x")) == []

async def test_release_snapshot_captures_current_release_scope(tmp_path) -> None:
    from know_your_project.domain.artifacts import Provenance
    from know_your_project.revisions.models import FactVersion

    store = SqliteRevisionStore(str(tmp_path / "state.db"))
    await store.initialize()
    fact = FactVersion(
        edge_uuid="edge-1",
        artifact_id=ArtifactId("a"),
        scope="release",
        subject="PaymentRetry",
        predicate="max_attempts",
        value="3",
        confidence=1.0,
        valid_from=datetime(2026, 9, 1, tzinfo=UTC),
        provenance=Provenance(source_kind="git", source_id="a", release_id=ReleaseId("v1")),
    )
    await store.replace_active_facts(ProjectId("p"), ArtifactId("a"), [fact], "release")
    await store.snapshot_release(ProjectId("p"), ReleaseId("v1"))
    snapshot = await store.get_release_snapshot(ProjectId("p"), ReleaseId("v1"))
    assert [(f.subject, f.predicate, f.value) for f in snapshot] == [
        ("PaymentRetry", "max_attempts", "3")
    ]
