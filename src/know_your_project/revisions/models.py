from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

from know_your_project.domain.artifacts import Provenance
from know_your_project.domain.ids import ArtifactId, ProjectId, ReleaseId


class Release(BaseModel):
    project_id: ProjectId
    release_id: ReleaseId
    tag: str = Field(min_length=1)
    commit_sha: str = Field(pattern=r"^[0-9a-fA-F]{40}$")
    effective_at: datetime
    predecessor: ReleaseId | None = None


class BranchState(BaseModel):
    project_id: ProjectId
    branch: str
    commit_sha: str = Field(pattern=r"^[0-9a-fA-F]{40}$")
    observed_at: datetime


class FactVersion(BaseModel):
    edge_uuid: str
    artifact_id: ArtifactId
    subject: str
    predicate: str
    value: str
    object_ref: str | None = None
    confidence: float
    valid_from: datetime
    valid_to: datetime | None = None
    provenance: Provenance


class UpsertFact(BaseModel):
    kind: Literal["upsert"] = "upsert"
    fact: FactVersion


class InvalidateFact(BaseModel):
    kind: Literal["invalidate"] = "invalidate"
    edge_uuid: str
    invalid_at: datetime


GraphMutation = UpsertFact | InvalidateFact


class RevisionPlan(BaseModel):
    mutations: list[GraphMutation]
    active_versions: list[FactVersion]
