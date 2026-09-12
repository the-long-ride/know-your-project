import pytest


@pytest.fixture
async def app_services(tmp_path):
    from tests.integration.support import AppServices
    services = await AppServices.create(tmp_path)
    return services


class AppHarness:
    def __init__(self, services) -> None:
        self.services = services

    async def search(self, text: str, project: str, release: str | None = None):
        return await self.services.tools.search_project_knowledge(text, project, release)


@pytest.fixture
async def app_harness(app_services) -> AppHarness:
    return AppHarness(app_services)
