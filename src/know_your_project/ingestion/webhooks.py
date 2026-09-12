import hmac
from typing import Any

from pydantic import BaseModel

from know_your_project.ingestion.reconciliation import ReconciliationService


class PushEvent(BaseModel):
    repository: str
    ref: str
    old_sha: str
    new_sha: str


class WorkItemEvent(BaseModel):
    work_item_id: int
    revision: str
    deleted: bool = False


def verify_webhook_secret(actual: str | None, expected: str) -> None:
    if actual is None or not hmac.compare_digest(actual, expected):
        raise PermissionError("invalid webhook secret")


def parse_push_event(payload: dict[str, Any]) -> PushEvent:
    resource = payload["resource"]
    update = resource["refUpdates"][0]
    return PushEvent(
        repository=resource["repository"]["id"],
        ref=update["name"],
        old_sha=update["oldObjectId"],
        new_sha=update["newObjectId"],
    )


def parse_work_item_event(payload: dict[str, Any]) -> WorkItemEvent:
    event_type = str(payload.get("eventType", "")).casefold()
    if not event_type.startswith("workitem."):
        raise ValueError(f"unsupported work item event: {event_type}")
    resource = payload["resource"]
    return WorkItemEvent(
        work_item_id=int(resource["id"]),
        revision=str(resource.get("rev", "")),
        deleted=event_type == "workitem.deleted",
    )


class AzureDevOpsWebhookHandler:
    def __init__(self, *, project: str, reconciliation: ReconciliationService) -> None:
        self._project = project
        self._reconciliation = reconciliation

    async def handle_push(self, event: PushEvent) -> None:
        await self._reconciliation.sync_ref(
            self._project,
            event.repository,
            event.ref,
            event.old_sha,
            event.new_sha,
        )

    async def handle_work_item(self, event: WorkItemEvent) -> None:
        if event.deleted:
            await self._reconciliation.delete_work_item(
                self._project, event.work_item_id, revision=event.revision
            )
            return
        await self._reconciliation.sync_work_item(self._project, event.work_item_id)
