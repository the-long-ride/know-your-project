from datetime import UTC, datetime
from typing import Literal

from know_your_project.domain.artifacts import SourceArtifact
from know_your_project.domain.ids import ArtifactId, ProjectId, ReleaseId
from know_your_project.ingestion.azure_devops.client import AzureDevOpsClient
from know_your_project.ingestion.azure_devops.mapper import work_item_artifact
from know_your_project.ingestion.checkpoints import SqliteCheckpointStore
from know_your_project.ingestion.pipeline import IngestionPipeline
from know_your_project.revisions.models import Release
from know_your_project.revisions.store import SqliteRevisionStore

_DOC_SUFFIXES = (".md", ".txt", ".rst")
_HTML_SUFFIXES = (".html", ".htm")
_SOURCE_SUFFIXES = (".cs", ".py", ".ts", ".tsx", ".js", ".java", ".go", ".rs")
_ZERO_SHA = "0" * 40
_WORK_ITEM_REPOSITORY = "__work_items__"
ArtifactKind = Literal["source", "document", "html"]


def _kind_for_path(path: str) -> ArtifactKind | None:
    lower = path.casefold()
    if lower.endswith(_DOC_SUFFIXES):
        return "document"
    if lower.endswith(_HTML_SUFFIXES):
        return "html"
    if lower.endswith(_SOURCE_SUFFIXES):
        return "source"
    return None


class ReconciliationService:
    def __init__(
        self,
        *,
        client: AzureDevOpsClient,
        checkpoints: SqliteCheckpointStore,
        pipeline: IngestionPipeline,
        revision_store: SqliteRevisionStore | None = None,
    ) -> None:
        self._client = client
        self._checkpoints = checkpoints
        self._pipeline = pipeline
        self._revision_store = revision_store

    async def _artifact(
        self,
        project: str,
        repository: str,
        path: str,
        revision: str,
        *,
        deleted: bool = False,
    ) -> SourceArtifact | None:
        kind = _kind_for_path(path)
        if kind is None:
            return None
        content = "" if deleted else await self._client.file_text(repository, path, revision)
        return SourceArtifact(
            project_id=ProjectId(project),
            artifact_id=ArtifactId(f"git:{repository}:{path}"),
            kind=kind,
            revision=revision,
            content=content,
            observed_at=datetime.now(UTC),
            path=path,
            repository=repository,
            commit_sha=revision,
            deleted=deleted,
        )

    async def collect_git_artifacts(
        self,
        project: str,
        repository: str,
        old_sha: str,
        new_sha: str,
    ) -> list[SourceArtifact]:
        items = await self._client.changed_files(repository, old_sha, new_sha)
        output: list[SourceArtifact] = []
        for item in items:
            artifact = await self._artifact(
                project,
                repository,
                item.path,
                new_sha,
                deleted=item.change_type.casefold() == "delete",
            )
            if artifact is not None:
                output.append(artifact)
        return output

    async def collect_full_artifacts(
        self, project: str, repository: str, new_sha: str
    ) -> list[SourceArtifact]:
        output: list[SourceArtifact] = []
        for path in await self._client.list_files(repository, new_sha):
            artifact = await self._artifact(project, repository, path, new_sha)
            if artifact is not None:
                output.append(artifact)
        return output

    async def sync_work_item(
        self, project: str, work_item_id: int
    ) -> SourceArtifact | None:
        payload = await self._client.get_work_item(work_item_id)
        revision = str(payload["rev"])
        key = str(work_item_id)
        known = await self._checkpoints.get(project, _WORK_ITEM_REPOSITORY, key)
        if known == revision:
            return None
        artifact = work_item_artifact(ProjectId(project), payload)
        await self._pipeline.persist_project_artifact(ProjectId(project), artifact)
        await self._checkpoints.set(project, _WORK_ITEM_REPOSITORY, key, revision)
        return artifact

    async def delete_work_item(
        self, project: str, work_item_id: int, *, revision: str
    ) -> None:
        artifact = SourceArtifact(
            project_id=ProjectId(project),
            artifact_id=ArtifactId(f"work-item:{work_item_id}"),
            kind="work_item",
            revision=revision,
            content="",
            observed_at=datetime.now(UTC),
            deleted=True,
        )
        await self._pipeline.persist_project_artifact(ProjectId(project), artifact)
        await self._checkpoints.delete(
            project, _WORK_ITEM_REPOSITORY, str(work_item_id)
        )

    async def reconcile_work_items(
        self, project: str, work_item_types: tuple[str, ...]
    ) -> None:
        current_ids = set(await self._client.list_work_item_ids(work_item_types))
        known = await self._checkpoints.list_for_repository(project, _WORK_ITEM_REPOSITORY)
        for work_item_id in sorted(current_ids):
            await self.sync_work_item(project, work_item_id)
        for key, revision in known.items():
            if key.isdigit() and int(key) not in current_ids:
                await self.delete_work_item(
                    project,
                    int(key),
                    revision=f"reconciled-delete:{revision}",
                )

    async def _release_for_tag(
        self, project: str, repository: str, ref: str, new_sha: str
    ) -> tuple[Release, str | None]:
        if self._revision_store is None:
            raise RuntimeError("revision store required for release tags")
        project_id = ProjectId(project)
        previous = await self._revision_store.get_latest_release(project_id)
        commit = await self._client.get_commit(repository, new_sha)
        raw_date = (commit.get("committer") or {}).get("date")
        effective_at = (
            datetime.fromisoformat(str(raw_date))
            if raw_date
            else datetime.now(UTC)
        )
        tag = ref.removeprefix("refs/tags/")
        release = Release(
            project_id=project_id,
            release_id=ReleaseId(tag),
            tag=tag,
            commit_sha=new_sha,
            effective_at=effective_at,
            predecessor=previous.release_id if previous else None,
        )
        await self._revision_store.save_release(release)
        await self._revision_store.set_release_status(
            project_id, release.release_id, "indexing"
        )
        return release, previous.commit_sha if previous else None

    async def sync_ref(
        self,
        project: str,
        repository: str,
        ref: str,
        old_sha: str | None,
        new_sha: str,
    ) -> None:
        release = None
        base_sha = old_sha
        if ref.startswith("refs/tags/"):
            release, base_sha = await self._release_for_tag(
                project, repository, ref, new_sha
            )

        if base_sha is None or base_sha == _ZERO_SHA:
            artifacts = await self.collect_full_artifacts(project, repository, new_sha)
        else:
            artifacts = await self.collect_git_artifacts(
                project, repository, base_sha, new_sha
            )

        try:
            await self._pipeline.persist(
                project_id=project,
                repository_name=repository,
                ref=ref,
                sha=new_sha,
                artifacts=artifacts,
                release=release,
            )
        except Exception:
            if release is not None and self._revision_store is not None:
                await self._revision_store.set_release_status(
                    ProjectId(project), release.release_id, "failed"
                )
            raise
        if release is not None and self._revision_store is not None:
            await self._revision_store.set_release_status(
                ProjectId(project), release.release_id, "ready"
            )

    async def reconcile_refs(
        self,
        project: str,
        repository: str,
        tracked_refs: set[str],
        release_tag_prefix: str = "refs/tags/",
    ) -> None:
        for ref in await self._client.list_refs(repository):
            if ref.name not in tracked_refs and not ref.name.startswith(release_tag_prefix):
                continue
            known = await self._checkpoints.get(project, repository, ref.name)
            if known != ref.object_id:
                await self.sync_ref(project, repository, ref.name, known, ref.object_id)
