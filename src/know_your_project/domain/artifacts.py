from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

from .ids import ArtifactId, ProjectId, ReleaseId


class Provenance(BaseModel):
    source_kind: Literal["git", "work_item", "document", "html"]
    source_id: str
    repository: str | None = None
    path: str | None = None
    commit_sha: str | None = None
    work_item_id: int | None = None
    release_id: ReleaseId | None = None


class SourceArtifact(BaseModel):
    project_id: ProjectId
    artifact_id: ArtifactId
    kind: Literal["source", "work_item", "document", "html"]
    revision: str
    content: str
    observed_at: datetime
    path: str | None = None
    repository: str | None = None
    commit_sha: str | None = None


class FactCandidate(BaseModel):
    subject: str = Field(min_length=1)
    predicate: str = Field(min_length=1)
    value: str = Field(min_length=1)
    object_ref: str | None = None
    confidence: float = Field(ge=0.0, le=1.0)
    provenance: Provenance
