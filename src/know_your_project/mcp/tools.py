from fastmcp.server.dependencies import get_access_token

from know_your_project.domain.ids import ProjectId, ReleaseId, WorkItemId
from know_your_project.domain.queries import ReleaseComparisonQuery, ReleaseKnowledgeQuery
from know_your_project.security.principal import principal_from_claims
from know_your_project.security.projection import project_result


class KnowledgeTools:
    def __init__(self, *, revisions, authorization) -> None:
        self._revisions = revisions
        self._authorization = authorization

    def _principal(self):
        token = get_access_token()
        if token is None:
            raise PermissionError("authentication required")
        return principal_from_claims(token.claims)

    def _authorize(self, project: str) -> ProjectId:
        project_id = ProjectId(project)
        self._authorization.require_project(self._principal(), project_id)
        return project_id

    async def search_project_knowledge(
        self, query: str, project: str, release: str | None = None
    ):
        project_id = self._authorize(project)
        results = await self._revisions.search(ReleaseKnowledgeQuery(
            project_id=project_id,
            text=query,
            release_id=ReleaseId(release) if release else None,
        ))
        return [project_result(r) for r in results]

    async def get_feature(self, name: str, project: str, release: str | None = None):
        return await self.search_project_knowledge(f"feature {name}", project, release)

    async def get_component(self, name: str, project: str, release: str | None = None):
        return await self.search_project_knowledge(f"component {name}", project, release)

    async def get_screen_spec(self, screen: str, project: str, release: str | None = None):
        return await self.search_project_knowledge(f"screen {screen}", project, release)

    async def get_release_changes(self, release: str, project: str):
        project_id = self._authorize(project)
        results = await self._revisions.release_changes(project_id, ReleaseId(release))
        return [project_result(r) for r in results]

    async def compare_releases(
        self,
        from_release: str,
        to_release: str,
        project: str,
        component: str | None = None,
    ):
        project_id = self._authorize(project)
        return await self._revisions.compare(ReleaseComparisonQuery(
            project_id=project_id,
            from_release=ReleaseId(from_release),
            to_release=ReleaseId(to_release),
            component=component,
        ))

    async def trace_work_item(
        self, work_item_id: int, project: str, release: str | None = None
    ):
        project_id = self._authorize(project)
        results = await self._revisions.trace_work_item(
            project_id,
            WorkItemId(work_item_id),
            ReleaseId(release) if release else None,
        )
        return [project_result(r) for r in results]
