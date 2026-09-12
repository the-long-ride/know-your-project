from unittest.mock import AsyncMock

from know_your_project.ingestion.models import GitRef
from know_your_project.ingestion.reconciliation import ReconciliationService


async def test_reconcile_refs_processes_only_changed_tracked_refs() -> None:
    client = AsyncMock()
    client.list_refs.return_value = [
        GitRef(name="refs/heads/main", object_id="b" * 40),
        GitRef(name="refs/heads/dev", object_id="c" * 40),
    ]
    checkpoints = AsyncMock()
    checkpoints.get.return_value = "a" * 40
    svc = ReconciliationService(client=client, checkpoints=checkpoints, pipeline=AsyncMock())
    svc.sync_ref = AsyncMock()  # type: ignore[method-assign]
    await svc.reconcile_refs("p", "r", {"refs/heads/main"})
    svc.sync_ref.assert_awaited_once_with(
        "p", "r", "refs/heads/main", "a" * 40, "b" * 40
    )
