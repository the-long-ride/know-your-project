from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

import pytest

from know_your_project.domain.ids import ArtifactId
from know_your_project.ingestion.pipeline import IngestionPipeline
from know_your_project.revisions.models import RevisionPlan


async def test_checkpoint_not_advanced_when_graph_write_fails() -> None:
    repository = AsyncMock()
    repository.apply.side_effect = RuntimeError("graph failed")
    extraction = AsyncMock()
    extraction.extract.return_value = []
    revision_store = AsyncMock()
    revision_store.get_active_facts.return_value = []
    engine = Mock()
    engine.plan.return_value = RevisionPlan(mutations=[], active_versions=[])
    checkpoints = AsyncMock()
    pipeline = IngestionPipeline(
        extraction=extraction,
        revision_engine=engine,
        revision_store=revision_store,
        repository=repository,
        checkpoints=checkpoints,
    )
    artifact = SimpleNamespace(artifact_id=ArtifactId("a"))
    with pytest.raises(RuntimeError):
        await pipeline.persist(
            project_id="p",
            repository_name="r",
            ref="main",
            sha="a" * 40,
            artifacts=[artifact],
            release=None,
        )
    checkpoints.set.assert_not_awaited()


async def test_release_snapshot_is_created_before_checkpoint() -> None:
    from datetime import UTC, datetime

    from know_your_project.domain.ids import ProjectId, ReleaseId
    from know_your_project.revisions.models import Release

    repository = AsyncMock()
    extraction = AsyncMock()
    extraction.extract.return_value = []
    revision_store = AsyncMock()
    revision_store.get_active_facts.return_value = []
    engine = Mock()
    engine.plan.return_value = RevisionPlan(mutations=[], active_versions=[])
    checkpoints = AsyncMock()
    pipeline = IngestionPipeline(
        extraction=extraction,
        revision_engine=engine,
        revision_store=revision_store,
        repository=repository,
        checkpoints=checkpoints,
    )
    artifact = SimpleNamespace(artifact_id=ArtifactId("a"))
    release = Release(
        project_id=ProjectId("p"), release_id=ReleaseId("v1"), tag="v1",
        commit_sha="a" * 40, effective_at=datetime(2026, 9, 1, tzinfo=UTC),
    )
    await pipeline.persist(
        project_id="p", repository_name="r", ref="refs/tags/v1", sha="a" * 40,
        artifacts=[artifact], release=release,
    )
    revision_store.snapshot_release.assert_awaited_once_with(ProjectId("p"), ReleaseId("v1"))
    checkpoints.set.assert_awaited_once()
