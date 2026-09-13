import httpx
import respx

from know_your_project.ingestion.azure_devops import client as client_module
from know_your_project.ingestion.azure_devops.client import AzureDevOpsClient


@respx.mock
async def test_list_refs() -> None:
    respx.get("https://dev.azure.com/acme/P/_apis/git/repositories/r/refs").mock(
        return_value=httpx.Response(200, json={"value": [
            {"name": "refs/heads/main", "objectId": "a" * 40}
        ]})
    )
    client = AzureDevOpsClient(base_url="https://dev.azure.com/acme", project="P", token="t")
    refs = await client.list_refs("r")
    await client.aclose()
    assert refs[0].object_id == "a" * 40


async def test_client_reuses_one_http_transport(monkeypatch) -> None:
    created = []

    class Response:
        def raise_for_status(self) -> None:
            pass

        def json(self):
            return {"value": []}

    class FakeClient:
        def __init__(self, **kwargs):
            created.append(kwargs)

        async def get(self, *args, **kwargs):
            return Response()

        async def aclose(self) -> None:
            pass

    monkeypatch.setattr(client_module.httpx, "AsyncClient", FakeClient)
    client = AzureDevOpsClient(base_url="https://dev.azure.com/acme", project="P", token="t")
    await client.list_refs("r")
    await client.list_refs("r")
    await client.aclose()
    assert len(created) == 1
