from datetime import UTC, datetime
from unittest.mock import AsyncMock

from know_your_project.domain.ids import ProjectId, ReleaseId
from know_your_project.domain.queries import ReleaseKnowledgeQuery
from know_your_project.revisions.models import Release
from know_your_project.revisions.queries import ReleaseQueryService


async def test_release_query_resolves_release_to_effective_time() -> None:
    repository = AsyncMock()
    repository.search.return_value = []
    store = AsyncMock()
    store.get_release.return_value = Release(
        project_id=ProjectId("p"), release_id=ReleaseId("v1"), tag="v1",
        commit_sha="a" * 40, effective_at=datetime(2026, 9, 1, tzinfo=UTC),
    )
    service = ReleaseQueryService(repository, store)
    await service.search(ReleaseKnowledgeQuery(
        project_id=ProjectId("p"), text="retry", release_id=ReleaseId("v1")
    ))
    query = repository.search.await_args.args[0]
    assert query.as_of == datetime(2026, 9, 1, tzinfo=UTC)
