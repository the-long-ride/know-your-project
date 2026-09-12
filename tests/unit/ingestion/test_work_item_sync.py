from unittest.mock import AsyncMock

from know_your_project.domain.ids import ProjectId
from know_your_project.ingestion.reconciliation import ReconciliationService
from know_your_project.ingestion.webhooks import (
    AzureDevOpsWebhookHandler,
    parse_work_item_event,
)


def work_item_payload(revision: int = 7) -> dict:
    return {
        "id": 42,
        "rev": revision,
        "fields": {
            "System.WorkItemType": "Product Backlog Item",
            "System.Title": "Payment retry",
            "System.State": "Active",
            "System.ChangedDate": "2026-09-12T07:00:00Z",
        },
    }


async def test_sync_work_item_persists_new_revision_and_skips_duplicate() -> None:
    client = AsyncMock()
    client.get_work_item.return_value = work_item_payload()
    checkpoints = AsyncMock()
    checkpoints.get.side_effect = [None, "7"]
    pipeline = AsyncMock()
    service = ReconciliationService(
        client=client, checkpoints=checkpoints, pipeline=pipeline, revision_store=AsyncMock()
    )

    artifact = await service.sync_work_item("payments", 42)
    assert artifact is not None
    pipeline.persist_project_artifact.assert_awaited_once_with(
        ProjectId("payments"), artifact
    )
    checkpoints.set.assert_awaited_once_with("payments", "__work_items__", "42", "7")

    pipeline.reset_mock()
    assert await service.sync_work_item("payments", 42) is None
    pipeline.persist_project_artifact.assert_not_awaited()


async def test_work_item_delete_retires_project_facts() -> None:
    service = ReconciliationService(
        client=AsyncMock(), checkpoints=AsyncMock(), pipeline=AsyncMock(), revision_store=AsyncMock()
    )
    await service.delete_work_item("payments", 42, revision="8")
    artifact = service._pipeline.persist_project_artifact.await_args.args[1]
    assert artifact.deleted is True
    assert str(artifact.artifact_id) == "work-item:42"


def test_work_item_event_uses_resource_id() -> None:
    event = parse_work_item_event({"eventType": "workitem.updated", "resource": {"id": 42, "rev": 7}})
    assert event.work_item_id == 42
    assert event.revision == "7"
    assert event.deleted is False


async def test_work_item_hook_routes_update_and_delete() -> None:
    reconciliation = AsyncMock()
    handler = AzureDevOpsWebhookHandler(project="payments", reconciliation=reconciliation)
    await handler.handle_work_item(parse_work_item_event(
        {"eventType": "workitem.updated", "resource": {"id": 42, "rev": 7}}
    ))
    reconciliation.sync_work_item.assert_awaited_once_with("payments", 42)

    await handler.handle_work_item(parse_work_item_event(
        {"eventType": "workitem.deleted", "resource": {"id": 42, "rev": 8}}
    ))
    reconciliation.delete_work_item.assert_awaited_once_with("payments", 42, revision="8")
