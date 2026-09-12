from datetime import datetime

from pydantic import BaseModel, Field


class SafeProvenance(BaseModel):
    source_kind: str
    source_id: str
    release_id: str | None = None


class KnowledgeResult(BaseModel):
    id: str
    kind: str = "fact"
    summary: str
    score: float | None = None
    valid_from: datetime | None = None
    valid_to: datetime | None = None
    provenance: list[SafeProvenance] = Field(default_factory=list)
