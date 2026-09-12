from know_your_project.domain.ids import ProjectId, ReleaseId, WorkItemId
from know_your_project.domain.queries import (
    KnowledgeQuery,
    ReleaseComparisonQuery,
    ReleaseKnowledgeQuery,
)
from know_your_project.revisions.models import FactVersion


def _slot(fact: FactVersion) -> tuple[str, str, str]:
    return (
        str(fact.artifact_id),
        fact.subject.strip().casefold(),
        fact.predicate.strip().casefold(),
    )


def _public_fact(fact: FactVersion) -> dict[str, str | None]:
    return {
        "subject": fact.subject,
        "predicate": fact.predicate,
        "value": fact.value,
        "object_ref": fact.object_ref,
    }


def _matches_component(fact: FactVersion, component: str | None) -> bool:
    if not component:
        return True
    needle = component.casefold()
    haystack = " ".join(
        [fact.subject, fact.predicate, fact.value, fact.object_ref or ""]
    ).casefold()
    return needle in haystack


class ReleaseQueryService:
    def __init__(self, repository, revision_store) -> None:
        self._repository = repository
        self._store = revision_store

    async def search(self, query: ReleaseKnowledgeQuery):
        if query.release_id is not None:
            release = await self._store.get_release(query.project_id, query.release_id)
            if release is None:
                raise KeyError(f"unknown release: {query.release_id}")
        else:
            release = await self._store.get_latest_release(query.project_id)
        as_of = release.effective_at if release is not None else None
        return await self._repository.search(KnowledgeQuery(
            project_id=query.project_id,
            text=query.text,
            as_of=as_of,
            scope="release",
            limit=query.limit,
        ))

    async def release_changes(self, project: ProjectId, release_id: ReleaseId):
        release = await self._store.get_release(project, release_id)
        if release is None:
            raise KeyError(f"unknown release: {release_id}")
        if release.predecessor is None:
            current = await self._store.get_release_snapshot(project, release_id)
            return {
                "release": str(release_id),
                "from_release": None,
                "added": [_public_fact(f) for f in current],
                "removed": [],
                "changed": [],
            }
        result = await self.compare(ReleaseComparisonQuery(
            project_id=project,
            from_release=release.predecessor,
            to_release=release_id,
        ))
        return {"release": str(release_id), **result}

    async def compare(self, query: ReleaseComparisonQuery):
        before = await self._store.get_release_snapshot(
            query.project_id, query.from_release
        )
        after = await self._store.get_release_snapshot(
            query.project_id, query.to_release
        )
        before_map = {
            _slot(f): f for f in before if _matches_component(f, query.component)
        }
        after_map = {
            _slot(f): f for f in after if _matches_component(f, query.component)
        }
        added = [
            _public_fact(after_map[key]) for key in sorted(after_map.keys() - before_map.keys())
        ]
        removed = [
            _public_fact(before_map[key]) for key in sorted(before_map.keys() - after_map.keys())
        ]
        changed: list[dict[str, str | None]] = []
        for key in sorted(before_map.keys() & after_map.keys()):
            old = before_map[key]
            new = after_map[key]
            if old.value == new.value and old.object_ref == new.object_ref:
                continue
            changed.append({
                "subject": new.subject,
                "predicate": new.predicate,
                "before": old.value,
                "after": new.value,
            })
        return {
            "from_release": str(query.from_release),
            "to_release": str(query.to_release),
            "added": added,
            "removed": removed,
            "changed": changed,
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
