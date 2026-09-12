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
