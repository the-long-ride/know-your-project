from collections import defaultdict
from datetime import UTC, datetime, timedelta
from pathlib import Path

from know_your_project.domain.artifacts import FactCandidate, Provenance
from know_your_project.domain.ids import ArtifactId, ProjectId, ReleaseId
from know_your_project.domain.queries import KnowledgeQuery
from know_your_project.ingestion.checkpoints import SqliteCheckpointStore
from know_your_project.ingestion.models import GitRef
from know_your_project.ingestion.reconciliation import ReconciliationService
from know_your_project.knowledge.dto import KnowledgeResult, SafeProvenance
from know_your_project.mcp.tools import KnowledgeTools
from know_your_project.revisions.engine import RevisionEngine
from know_your_project.revisions.models import FactVersion, InvalidateFact, Release, UpsertFact
from know_your_project.revisions.queries import ReleaseQueryService
from know_your_project.revisions.store import SqliteRevisionStore
from know_your_project.security.authorization import AuthorizationService
from know_your_project.security.principal import Principal


class MemoryKnowledgeRepository:
    def __init__(self) -> None:
        self._facts: dict[str, dict[str, FactVersion]] = defaultdict(dict)

    async def apply(self, project_id: str, mutations: list) -> None:
        facts = self._facts[project_id]
        for mutation in mutations:
            if isinstance(mutation, InvalidateFact):
                old = facts[mutation.edge_uuid]
                facts[mutation.edge_uuid] = old.model_copy(
                    update={"valid_to": mutation.invalid_at}
                )
            elif isinstance(mutation, UpsertFact):
                facts[mutation.fact.edge_uuid] = mutation.fact
            else:
                raise TypeError(type(mutation))

    async def search(self, query: KnowledgeQuery) -> list[KnowledgeResult]:
        terms = {
            token.casefold().replace("_", " ")
            for token in query.text.replace("-", " ").split()
            if token
        }
        ranked: list[tuple[int, KnowledgeResult]] = []
        for fact in self._facts[str(query.project_id)].values():
            if fact.scope != query.scope:
                continue
            if query.as_of is not None:
                if fact.valid_from > query.as_of:
                    continue
                if fact.valid_to is not None and fact.valid_to <= query.as_of:
                    continue
            elif fact.valid_to is not None:
                continue
            summary = f"{fact.subject} {fact.predicate}: {fact.value}"
            normalized = summary.casefold().replace("_", " ")
            score = sum(1 for term in terms if term in normalized)
            if terms and score == 0:
                continue
            ranked.append((score, KnowledgeResult(
                id=fact.edge_uuid,
                summary=summary,
                score=float(score),
                valid_from=fact.valid_from,
                valid_to=fact.valid_to,
                provenance=[SafeProvenance(
                    source_kind=fact.provenance.source_kind,
                    source_id=fact.provenance.source_id,
                    release_id=(
                        str(fact.provenance.release_id)
                        if fact.provenance.release_id else None
                    ),
                )],
            )))
        ranked.sort(key=lambda pair: pair[0], reverse=True)
        return [result for _, result in ranked[: query.limit]]


class FakeAzureClient:
    def __init__(self) -> None:
        self.refs: dict[str, str] = {}

    async def list_refs(self, repository: str) -> list[GitRef]:
        return [GitRef(name=name, object_id=sha) for name, sha in self.refs.items()]

    async def changed_files(self, repository: str, base: str, target: str) -> list:
        return []

    async def list_files(self, repository: str, version: str) -> list[str]:
        return []


class CheckpointPipeline:
    def __init__(self, checkpoints: SqliteCheckpointStore) -> None:
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
        await self._checkpoints.set(project_id, repository_name, ref, sha)


class AppServices:
    def __init__(self) -> None:
        self.project = ProjectId("payments")
        self.principal = Principal(subject="tester", projects={self.project})

    @classmethod
    async def create(cls, tmp_path: Path) -> "AppServices":
        self = cls()
        db = str(tmp_path / "state.db")
        self.revision_store = SqliteRevisionStore(db)
        self.checkpoints = SqliteCheckpointStore(db)
        await self.revision_store.initialize()
        await self.checkpoints.initialize()
        self.repository = MemoryKnowledgeRepository()
        self.engine = RevisionEngine()
        self.revisions = ReleaseQueryService(self.repository, self.revision_store)
        self.tools = KnowledgeTools(
            revisions=self.revisions,
            authorization=AuthorizationService(),
        )
        self.tools._principal = lambda: self.principal  # type: ignore[method-assign]
        self.azure = FakeAzureClient()
        self.reconciliation = ReconciliationService(
            client=self.azure,
            checkpoints=self.checkpoints,
            pipeline=CheckpointPipeline(self.checkpoints),
            revision_store=self.revision_store,
        )
        self._release_counter = 0
        return self

    def authenticate(self, *, projects: set[str]) -> None:
        self.principal = Principal(
            subject="tester",
            projects={ProjectId(project) for project in projects},
        )

    async def index_release(self, version: str, facts: dict[str, str]) -> None:
        previous_release = await self.revision_store.get_latest_release(self.project)
        effective_at = datetime(2026, 9, 1, tzinfo=UTC) + timedelta(
            days=self._release_counter
        )
        self._release_counter += 1
        release = Release(
            project_id=self.project,
            release_id=ReleaseId(version),
            tag=version,
            commit_sha=f"{self._release_counter:040x}",
            effective_at=effective_at,
            predecessor=(
                previous_release.release_id if previous_release is not None else None
            ),
        )
        await self.revision_store.save_release(release)
        await self.revision_store.set_release_status(
            self.project, release.release_id, "indexing"
        )

        grouped: dict[str, list[FactCandidate]] = defaultdict(list)
        for key, value in facts.items():
            subject, predicate = key.split(".", 1)
            grouped[subject].append(FactCandidate(
                subject=subject,
                predicate=predicate,
                value=value,
                confidence=1.0,
                provenance=Provenance(
                    source_kind="git",
                    source_id=f"fixture:{subject}",
                    release_id=release.release_id,
                ),
            ))

        for subject, candidates in grouped.items():
            artifact_id = ArtifactId(f"fixture:{subject}")
            previous = await self.revision_store.get_active_facts(
                self.project, artifact_id, "release"
            )
            plan = self.engine.plan(
                project_id=self.project,
                artifact_id=artifact_id,
                previous=previous,
                current=candidates,
                effective_at=effective_at,
                scope="release",
            )
            await self.repository.apply(str(self.project), plan.mutations)
            await self.revision_store.replace_active_facts(
                self.project, artifact_id, plan.active_versions, "release"
            )

        await self.revision_store.snapshot_release(self.project, release.release_id)
        await self.revision_store.set_release_status(
            self.project, release.release_id, "ready"
        )

    async def index_source(self, name: str, raw_source: str) -> None:
        # The acceptance harness deliberately emulates the production safe extraction boundary:
        # raw source is consumed to derive a semantic fact, but is never persisted or returned.
        artifact_id = ArtifactId(f"git:repo:/{name}")
        previous = await self.revision_store.get_active_facts(
            self.project, artifact_id, "release"
        )
        candidate = FactCandidate(
            subject=Path(name).stem,
            predicate="behavior",
            value="Contains sensitive implementation behavior",
            confidence=0.9,
            provenance=Provenance(
                source_kind="git",
                source_id=str(artifact_id),
            ),
        )
        plan = self.engine.plan(
            project_id=self.project,
            artifact_id=artifact_id,
            previous=previous,
            current=[candidate],
            effective_at=datetime(2026, 9, 1, tzinfo=UTC),
            scope="release",
        )
        await self.repository.apply(str(self.project), plan.mutations)
        await self.revision_store.replace_active_facts(
            self.project, artifact_id, plan.active_versions, "release"
        )
        assert raw_source not in str(plan.model_dump())

    async def set_checkpoint(self, repository: str, ref: str, sha: str) -> None:
        await self.checkpoints.set("payments", repository, ref, sha)

    async def get_checkpoint(self, repository: str, ref: str) -> str | None:
        return await self.checkpoints.get("payments", repository, ref)

    def set_remote_ref(self, repository: str, ref: str, sha: str) -> None:
        self.azure.refs[ref] = sha

    async def reconcile(self) -> None:
        await self.reconciliation.reconcile_refs(
            "payments", "repo", set(self.azure.refs)
        )
