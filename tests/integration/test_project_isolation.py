import pytest


async def test_principal_cannot_query_ungranted_project(app_harness) -> None:
    app_harness.services.authenticate(projects={"project-a"})
    with pytest.raises(PermissionError):
        await app_harness.search("billing", "project-b")
