import base64

import httpx

from know_your_project.ingestion.models import ChangedFile, GitRef


class AzureDevOpsClient:
    def __init__(self, *, base_url: str, project: str, token: str) -> None:
        self._root = f"{base_url.rstrip('/')}/{project}/_apis"
        encoded = base64.b64encode(f":{token}".encode()).decode()
        self._headers = {"Authorization": f"Basic {encoded}"}

    async def _get_json(self, path: str, params: dict[str, str] | None = None) -> dict:
        query = {"api-version": "7.1", **(params or {})}
        async with httpx.AsyncClient(headers=self._headers, timeout=60) as client:
            response = await client.get(f"{self._root}/{path}", params=query)
            response.raise_for_status()
            return response.json()

    async def list_refs(self, repository: str) -> list[GitRef]:
        body = await self._get_json(f"git/repositories/{repository}/refs")
        return [GitRef(name=x["name"], object_id=x["objectId"]) for x in body["value"]]

    async def changed_files(self, repository: str, base: str, target: str) -> list[ChangedFile]:
        body = await self._get_json(
            f"git/repositories/{repository}/diffs/commits",
            {"baseVersion": base, "targetVersion": target},
        )
        return [
            ChangedFile(path=x["item"]["path"], change_type=x["changeType"])
            for x in body.get("changes", [])
        ]

    async def file_text(self, repository: str, path: str, version: str) -> str:
        async with httpx.AsyncClient(headers=self._headers, timeout=60) as client:
            response = await client.get(
                f"{self._root}/git/repositories/{repository}/items",
                params={
                    "path": path,
                    "versionDescriptor.version": version,
                    "includeContent": "true",
                    "api-version": "7.1",
                },
            )
            response.raise_for_status()
            return response.text

    async def get_work_item(self, work_item_id: int) -> dict:
        return await self._get_json(
            f"wit/workitems/{work_item_id}", {"$expand": "relations"}
        )
