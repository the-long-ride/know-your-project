from datetime import UTC, datetime
from unittest.mock import AsyncMock

from know_your_project.domain.ids import ProjectId, ReleaseId
from know_your_project.domain.queries import ReleaseKnowledgeQuery
from know_your_project.knowledge.dto import KnowledgeResult
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
    query = repository.search.await_args_list[0].args[0]
    assert query.as_of == datetime(2026, 9, 1, tzinfo=UTC)


async def test_default_query_targets_latest_ready_release() -> None:
    repository = AsyncMock()
    repository.search.return_value = []
    store = AsyncMock()
    store.get_latest_release.return_value = Release(
        project_id=ProjectId("p"), release_id=ReleaseId("v2"), tag="v2",
        commit_sha="b" * 40, effective_at=datetime(2026, 9, 2, tzinfo=UTC),
    )
    service = ReleaseQueryService(repository, store)
    await service.search(ReleaseKnowledgeQuery(project_id=ProjectId("p"), text="retry"))
    query = repository.search.await_args_list[0].args[0]
    assert query.as_of == datetime(2026, 9, 2, tzinfo=UTC)
    assert query.scope == "release"


async def test_project_work_item_knowledge_is_included_with_release_knowledge() -> None:
    release_result = KnowledgeResult(id="release-fact", summary="Payment retries 3 times")
    project_result = KnowledgeResult(id="pbi-fact", summary="PBI 42 requires payment retry")
    repository = AsyncMock()
    repository.search.side_effect = [[release_result], [project_result]]
    store = AsyncMock()
    store.get_latest_release.return_value = Release(
        project_id=ProjectId("p"), release_id=ReleaseId("v2"), tag="v2",
        commit_sha="b" * 40, effective_at=datetime(2026, 9, 2, tzinfo=UTC),
    )
    service = ReleaseQueryService(repository, store)

    results = await service.search(
        ReleaseKnowledgeQuery(project_id=ProjectId("p"), text="payment retry")
    )

    assert [call.args[0].scope for call in repository.search.await_args_list] == [
        "release",
        "project",
    ]
    assert [result.id for result in results] == ["release-fact", "pbi-fact"]


async def test_compare_releases_uses_exact_snapshots_not_semantic_search() -> None:
    from know_your_project.domain.artifacts import Provenance
    from know_your_project.domain.ids import ArtifactId
    from know_your_project.domain.queries import ReleaseComparisonQuery
    from know_your_project.revisions.models import FactVersion

    def version(value: str, release: str) -> FactVersion:
        return FactVersion(
            edge_uuid=f"e-{release}", artifact_id=ArtifactId("payment"), scope="release",
            subject="PaymentRetry", predicate="max_attempts", value=value, confidence=1.0,
            valid_from=datetime(2026, 9, 1, tzinfo=UTC),
            provenance=Provenance(source_kind="git", source_id="payment", release_id=ReleaseId(release)),
        )

    repository = AsyncMock()
    store = AsyncMock()
    store.get_release_snapshot.side_effect = [[version("3", "v1")], [version("5", "v2")]]
    service = ReleaseQueryService(repository, store)
    result = await service.compare(ReleaseComparisonQuery(
        project_id=ProjectId("p"), from_release=ReleaseId("v1"), to_release=ReleaseId("v2")
    ))
    assert result["changed"] == [{
        "subject": "PaymentRetry", "predicate": "max_attempts", "before": "3", "after": "5"
    }]
    repository.search.assert_not_awaited()
