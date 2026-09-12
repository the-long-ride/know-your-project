import pytest

from know_your_project.domain.ids import ProjectId
from know_your_project.knowledge.dto import KnowledgeResult
from know_your_project.security.authorization import AuthorizationError, AuthorizationService
from know_your_project.security.principal import Principal, principal_from_claims
from know_your_project.security.projection import project_result


def test_project_access_denied_by_default() -> None:
    with pytest.raises(AuthorizationError):
        AuthorizationService().require_project(
            Principal(subject="alice", projects={ProjectId("a")}), ProjectId("b")
        )


def test_projection_is_allowlist_only() -> None:
    value = project_result(KnowledgeResult(id="x", summary="semantic behavior"))
    assert set(value) == {"id", "kind", "summary", "score", "valid_from", "valid_to", "provenance"}


def test_claims_require_subject_and_list_projects() -> None:
    principal = principal_from_claims({"sub": "alice", "projects": ["a", "b"]})
    assert principal.projects == {ProjectId("a"), ProjectId("b")}
    with pytest.raises(PermissionError):
        principal_from_claims({"projects": ["a"]})
