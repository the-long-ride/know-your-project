from know_your_project.domain.ids import ProjectId, ReleaseId, WorkItemId
from know_your_project.domain.queries import (
    KnowledgeQuery,
    ReleaseComparisonQuery,
    ReleaseKnowledgeQuery,
)


class ReleaseQueryService:
    def __init__(self, repository, revision_store) -> None:
        self._repository = repository
        self._store = revision_store

    async def search(self, query: ReleaseKnowledgeQuery):
        as_of = None
        if query.release_id is not None:
            release = await self._store.get_release(query.project_id, query.release_id)
            if release is None:
                raise KeyError(f"unknown release: {query.release_id}")
            as_of = release.effective_at
        return await self._repository.search(KnowledgeQuery(
            project_id=query.project_id,
            text=query.text,
            as_of=as_of,
            limit=query.limit,
        ))

    async def release_changes(self, project: ProjectId, release_id: ReleaseId):
        release = await self._store.get_release(project, release_id)
        if release is None:
            raise KeyError(f"unknown release: {release_id}")
        return await self._repository.search(KnowledgeQuery(
            project_id=project,
            text="changed introduced removed behavior",
            as_of=release.effective_at,
            limit=50,
        ))

    async def compare(self, query: ReleaseComparisonQuery):
        before = await self.search(ReleaseKnowledgeQuery(
            project_id=query.project_id,
            text=query.component or "feature behavior requirement",
            release_id=query.from_release,
            limit=50,
        ))
        after = await self.search(ReleaseKnowledgeQuery(
            project_id=query.project_id,
            text=query.component or "feature behavior requirement",
            release_id=query.to_release,
            limit=50,
        ))
        before_map = {r.summary: r for r in before}
        after_map = {r.summary: r for r in after}
        return {
            "from_release": str(query.from_release),
            "to_release": str(query.to_release),
            "removed": list(before_map.keys() - after_map.keys()),
            "added": list(after_map.keys() - before_map.keys()),
        }

    async def trace_work_item(
        self,
        project: ProjectId,
        work_item_id: WorkItemId,
        release_id: ReleaseId | None,
    ):
        return await self.search(ReleaseKnowledgeQuery(
            project_id=project,
            text=f"work-item:{int(work_item_id)} PBI-{int(work_item_id)}",
            release_id=release_id,
            limit=50,
        ))
