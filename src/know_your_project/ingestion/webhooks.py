import hmac
from typing import Any

from pydantic import BaseModel

from know_your_project.ingestion.reconciliation import ReconciliationService


class PushEvent(BaseModel):
    repository: str
    ref: str
    old_sha: str
    new_sha: str


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
