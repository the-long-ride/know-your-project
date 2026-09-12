import base64
from typing import Any, cast

import httpx

from know_your_project.ingestion.models import ChangedFile, GitRef


class AzureDevOpsClient:
    def __init__(self, *, base_url: str, project: str, token: str) -> None:
        self._root = f"{base_url.rstrip('/')}/{project}/_apis"
        encoded = base64.b64encode(f":{token}".encode()).decode()
        self._headers = {"Authorization": f"Basic {encoded}"}

    async def _get_json(
        self, path: str, params: dict[str, str] | None = None
    ) -> dict[str, Any]:
        query = {"api-version": "7.1", **(params or {})}
        async with httpx.AsyncClient(headers=self._headers, timeout=60) as client:
            response = await client.get(f"{self._root}/{path}", params=query)
            response.raise_for_status()
            return cast(dict[str, Any], response.json())

    async def _post_json(self, path: str, payload: dict[str, Any]) -> dict[str, Any]:
        async with httpx.AsyncClient(headers=self._headers, timeout=60) as client:
            response = await client.post(
                f"{self._root}/{path}",
                params={"api-version": "7.1"},
                json=payload,
            )
            response.raise_for_status()
            return cast(dict[str, Any], response.json())

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

    async def list_files(self, repository: str, version: str) -> list[str]:
        body = await self._get_json(
            f"git/repositories/{repository}/items",
            {
                "scopePath": "/",
                "recursionLevel": "Full",
                "includeContentMetadata": "true",
                "versionDescriptor.version": version,
                "versionDescriptor.versionType": "commit",
            },
        )
        return [
            str(item["path"])
            for item in body.get("value", [])
            if not item.get("isFolder", False)
        ]

    async def get_commit(self, repository: str, commit_sha: str) -> dict[str, Any]:
        return await self._get_json(f"git/repositories/{repository}/commits/{commit_sha}")

    async def get_work_item(self, work_item_id: int) -> dict[str, Any]:
        return await self._get_json(
            f"wit/workitems/{work_item_id}", {"$expand": "relations"}
        )

    async def list_work_item_ids(self, work_item_types: tuple[str, ...]) -> list[int]:
        if not work_item_types:
            return []
        quoted = ", ".join(
            f"'{item.replace(chr(39), chr(39) * 2)}'" for item in work_item_types
        )
        body = await self._post_json(
            "wit/wiql",
            {"query": f"SELECT [System.Id] FROM WorkItems WHERE [System.WorkItemType] IN ({quoted})"},
        )
        return [int(item["id"]) for item in body.get("workItems", [])]
