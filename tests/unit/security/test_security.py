import pytest

from know_your_project.domain.ids import ProjectId
from know_your_project.knowledge.dto import KnowledgeResult, SafeProvenance
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


def test_projection_replaces_internal_source_id_with_opaque_reference() -> None:
    value = project_result(KnowledgeResult(
        id="x",
        summary="semantic behavior",
        provenance=[SafeProvenance(
            source_kind="git",
            source_id="git:payments:/src/private/SecretService.cs",
            release_id="v1.2.3",
        )],
    ))
    serialized = str(value)
    assert "SecretService.cs" not in serialized
    assert "/src/private" not in serialized
    provenance = value["provenance"][0]
    assert "source_id" not in provenance
    assert str(provenance["reference_id"]).startswith("ref:")
    assert provenance["release_id"] == "v1.2.3"


def test_claims_require_subject_and_list_projects() -> None:
    principal = principal_from_claims({"sub": "alice", "projects": ["a", "b"]})
    assert principal.projects == {ProjectId("a"), ProjectId("b")}
    with pytest.raises(PermissionError):
        principal_from_claims({"projects": ["a"]})
