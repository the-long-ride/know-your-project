from datetime import datetime
from uuid import NAMESPACE_URL, uuid5

from know_your_project.domain.artifacts import FactCandidate
from know_your_project.domain.ids import ArtifactId, ProjectId

from .models import FactVersion, InvalidateFact, RevisionPlan, UpsertFact


def _slot(subject: str, predicate: str) -> tuple[str, str]:
    return subject.strip().casefold(), predicate.strip().casefold()


def _version_uuid(
    project_id: ProjectId,
    artifact_id: ArtifactId,
    candidate: FactCandidate,
    effective_at: datetime,
    scope: str,
) -> str:
    raw = "|".join([
        str(project_id),
        scope,
        str(artifact_id),
        candidate.subject.strip().casefold(),
        candidate.predicate.strip().casefold(),
        candidate.value.strip(),
        candidate.object_ref or "",
        effective_at.isoformat(),
    ])
    return str(uuid5(NAMESPACE_URL, raw))


class RevisionEngine:
    def plan(
        self,
        *,
        project_id: ProjectId,
        artifact_id: ArtifactId,
        previous: list[FactVersion],
        current: list[FactCandidate],
        effective_at: datetime,
        scope: str = "release",
    ) -> RevisionPlan:
        old = {_slot(f.subject, f.predicate): f for f in previous if f.valid_to is None}
        new = {_slot(f.subject, f.predicate): f for f in current}
        mutations: list[InvalidateFact | UpsertFact] = []
        active: list[FactVersion] = []

        for key, old_fact in old.items():
            candidate = new.get(key)
            same = candidate is not None and (
                candidate.value == old_fact.value and candidate.object_ref == old_fact.object_ref
            )
            if same:
                active.append(old_fact)
            else:
                mutations.append(InvalidateFact(edge_uuid=old_fact.edge_uuid, invalid_at=effective_at))

        for key, candidate in new.items():
            old_fact = old.get(key)
            same = old_fact is not None and (
                old_fact.value == candidate.value and old_fact.object_ref == candidate.object_ref
            )
            if same:
                continue
            version = FactVersion(
                edge_uuid=_version_uuid(project_id, artifact_id, candidate, effective_at, scope),
                artifact_id=artifact_id,
                scope=scope,
                subject=candidate.subject,
                predicate=candidate.predicate,
                value=candidate.value,
                object_ref=candidate.object_ref,
                confidence=candidate.confidence,
                valid_from=effective_at,
                provenance=candidate.provenance,
            )
            active.append(version)
            mutations.append(UpsertFact(fact=version))

        return RevisionPlan(mutations=mutations, active_versions=active)
