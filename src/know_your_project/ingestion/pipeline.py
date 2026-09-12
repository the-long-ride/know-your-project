from datetime import UTC, datetime

from know_your_project.domain.artifacts import SourceArtifact
from know_your_project.domain.ids import ArtifactId, ProjectId
from know_your_project.extraction.service import ExtractionService
from know_your_project.ingestion.checkpoints import SqliteCheckpointStore
from know_your_project.knowledge.interfaces import KnowledgeRepository
from know_your_project.revisions.engine import RevisionEngine
from know_your_project.revisions.models import Release, RevisionPlan
from know_your_project.revisions.store import SqliteRevisionStore


class IngestionPipeline:
    def __init__(
        self,
        *,
        extraction: ExtractionService,
        revision_engine: RevisionEngine,
        revision_store: SqliteRevisionStore,
        repository: KnowledgeRepository,
        checkpoints: SqliteCheckpointStore,
    ) -> None:
        self._extraction = extraction
        self._engine = revision_engine
        self._revision_store = revision_store
        self._repository = repository
        self._checkpoints = checkpoints

    async def persist(
        self,
        *,
        project_id: str,
        repository_name: str,
        ref: str,
        sha: str,
        artifacts: list[SourceArtifact],
        release: Release | None,
    ) -> None:
        project = ProjectId(project_id)
        effective_at = release.effective_at if release else datetime.now(UTC)
        scope = "release" if release else f"branch:{ref}"
        all_plans: list[tuple[ArtifactId, RevisionPlan]] = []
        for artifact in artifacts:
            candidates = await self._extraction.extract(artifact)
            if release:
                candidates = [
                    c.model_copy(update={
                        "provenance": c.provenance.model_copy(
                            update={"release_id": release.release_id}
                        )
                    })
                    for c in candidates
                ]
            previous = await self._revision_store.get_active_facts(
                project, artifact.artifact_id, scope
            )
            plan = self._engine.plan(
                project_id=project,
                artifact_id=artifact.artifact_id,
                previous=previous,
                current=candidates,
                effective_at=effective_at,
                scope=scope,
            )
            all_plans.append((artifact.artifact_id, plan))

        for _, plan in all_plans:
            await self._repository.apply(project_id, plan.mutations)
        for artifact_id, plan in all_plans:
            await self._revision_store.replace_active_facts(
                project, artifact_id, plan.active_versions, scope
            )
        if release is not None:
            await self._revision_store.snapshot_release(project, release.release_id)
        await self._checkpoints.set(project_id, repository_name, ref, sha)
