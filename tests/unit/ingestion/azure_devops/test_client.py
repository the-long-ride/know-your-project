import httpx
import respx

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
    assert refs[0].object_id == "a" * 40
