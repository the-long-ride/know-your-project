from datetime import UTC, datetime

from know_your_project.domain.ids import ProjectId


class IngestionPipeline:
    def __init__(
        self,
        *,
        extraction,
        revision_engine,
        revision_store,
        repository,
        checkpoints,
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
        artifacts: list,
        release,
    ) -> None:
        project = ProjectId(project_id)
        effective_at = release.effective_at if release else datetime.now(UTC)
        all_plans = []
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
                project, artifact.artifact_id
            )
            plan = self._engine.plan(
                project_id=project,
                artifact_id=artifact.artifact_id,
                previous=previous,
                current=candidates,
                effective_at=effective_at,
            )
            all_plans.append((artifact.artifact_id, plan))

        for _, plan in all_plans:
            await self._repository.apply(project_id, plan.mutations)
        for artifact_id, plan in all_plans:
            await self._revision_store.replace_active_facts(
                project, artifact_id, plan.active_versions
            )
        await self._checkpoints.set(project_id, repository_name, ref, sha)
