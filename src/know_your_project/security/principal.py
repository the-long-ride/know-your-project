from pydantic import BaseModel

from know_your_project.domain.ids import ProjectId


class Principal(BaseModel):
    subject: str
    projects: set[ProjectId]


def principal_from_claims(claims: dict) -> Principal:
    subject = str(claims.get("sub") or "")
    projects = claims.get("projects") or []
    if not subject:
        raise PermissionError("missing subject")
    if not isinstance(projects, list):
        raise PermissionError("projects claim must be a list")
    return Principal(subject=subject, projects={ProjectId(str(p)) for p in projects})
