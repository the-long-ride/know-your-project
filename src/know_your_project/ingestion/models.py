from datetime import datetime

from pydantic import BaseModel


class GitRef(BaseModel):
    name: str
    object_id: str


class ChangedFile(BaseModel):
    path: str
    change_type: str


class WorkItemRevision(BaseModel):
    id: int
    revision: int
    type: str
    title: str
    description: str = ""
    acceptance_criteria: str = ""
    state: str
    changed_at: datetime | None = None
