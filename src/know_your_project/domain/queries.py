from datetime import datetime

from pydantic import BaseModel, Field

from .ids import ProjectId, ReleaseId, WorkItemId


class KnowledgeQuery(BaseModel):
    project_id: ProjectId
    text: str = Field(min_length=1)
    as_of: datetime | None = None
    limit: int = Field(default=10, ge=1, le=50)


class ReleaseKnowledgeQuery(BaseModel):
    project_id: ProjectId
    text: str = Field(min_length=1)
    release_id: ReleaseId | None = None
    limit: int = Field(default=10, ge=1, le=50)


class ReleaseComparisonQuery(BaseModel):
    project_id: ProjectId
    from_release: ReleaseId
    to_release: ReleaseId
    component: str | None = None


class WorkItemTraceQuery(BaseModel):
    project_id: ProjectId
    work_item_id: WorkItemId
    release_id: ReleaseId | None = None
