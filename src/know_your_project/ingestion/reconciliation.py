from datetime import UTC, datetime

from know_your_project.domain.artifacts import SourceArtifact
from know_your_project.domain.ids import ArtifactId, ProjectId
from know_your_project.ingestion.azure_devops.mapper import work_item_artifact

_DOC_SUFFIXES = (".md", ".txt", ".rst")
_HTML_SUFFIXES = (".html", ".htm")
_SOURCE_SUFFIXES = (".cs", ".py", ".ts", ".tsx", ".js", ".java", ".go", ".rs")


def _kind_for_path(path: str) -> str | None:
    lower = path.casefold()
    if lower.endswith(_DOC_SUFFIXES):
        return "document"
    if lower.endswith(_HTML_SUFFIXES):
        return "html"
    if lower.endswith(_SOURCE_SUFFIXES):
        return "source"
    return None


class ReconciliationService:
    def __init__(self, *, client, checkpoints, pipeline) -> None:
        self._client = client
        self._checkpoints = checkpoints
        self._pipeline = pipeline

    async def collect_git_artifacts(
        self,
        project: str,
        repository: str,
        ref: str,
        old_sha: str,
        new_sha: str,
    ) -> list[SourceArtifact]:
        items = await self._client.changed_files(repository, old_sha, new_sha)
        output: list[SourceArtifact] = []
        for item in items:
            kind = _kind_for_path(item.path)
            if kind is None:
                continue
            deleted = item.change_type.casefold() == "delete"
            content = "" if deleted else await self._client.file_text(
                repository, item.path, new_sha
            )
            output.append(SourceArtifact(
                project_id=ProjectId(project),
                artifact_id=ArtifactId(f"git:{repository}:{item.path}"),
                kind=kind,
                revision=new_sha,
                content=content,
                observed_at=datetime.now(UTC),
                path=item.path,
                repository=repository,
                commit_sha=new_sha,
                deleted=deleted,
            ))
        return output

    async def sync_work_item(self, project: str, work_item_id: int) -> SourceArtifact:
        payload = await self._client.get_work_item(work_item_id)
        return work_item_artifact(ProjectId(project), payload)

    async def sync_ref(
        self,
        project: str,
        repository: str,
        ref: str,
        old_sha: str | None,
        new_sha: str,
    ) -> None:
        if old_sha is None:
            raise RuntimeError("initial repository backfill is not configured for this ref")
        artifacts = await self.collect_git_artifacts(
            project, repository, ref, old_sha, new_sha
        )
        await self._pipeline.persist(
            project_id=project,
            repository_name=repository,
            ref=ref,
            sha=new_sha,
            artifacts=artifacts,
            release=None,
        )

    async def reconcile_refs(
        self, project: str, repository: str, tracked_refs: set[str]
    ) -> None:
        for ref in await self._client.list_refs(repository):
            if ref.name not in tracked_refs:
                continue
            known = await self._checkpoints.get(project, repository, ref.name)
            if known != ref.object_id:
                await self.sync_ref(project, repository, ref.name, known, ref.object_id)
