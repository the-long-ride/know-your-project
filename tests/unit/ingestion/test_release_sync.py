from datetime import UTC, datetime
from unittest.mock import AsyncMock

from know_your_project.ingestion.models import ChangedFile
from know_your_project.ingestion.reconciliation import ReconciliationService
from know_your_project.revisions.models import Release


async def test_initial_branch_sync_backfills_supported_repository_files() -> None:
    client = AsyncMock()
    client.list_files.return_value = ["/src/App.cs", "/README.md", "/image.png"]
    client.file_text.side_effect = ["class App {}", "# Readme"]
    pipeline = AsyncMock()
    svc = ReconciliationService(
        client=client, checkpoints=AsyncMock(), pipeline=pipeline, revision_store=AsyncMock()
    )

    await svc.sync_ref("p", "r", "refs/heads/main", None, "b" * 40)

    persisted = pipeline.persist.await_args.kwargs
    assert [a.path for a in persisted["artifacts"]] == ["/src/App.cs", "/README.md"]
    assert persisted["release"] is None


async def test_release_tag_uses_previous_release_commit_and_records_release() -> None:
    client = AsyncMock()
    client.get_commit.return_value = {
        "committer": {"date": "2026-09-12T01:02:03Z"}
    }
    client.changed_files.return_value = [ChangedFile(path="/src/App.cs", change_type="edit")]
    client.file_text.return_value = "class App {}"
    store = AsyncMock()
    store.get_latest_release.return_value = Release(
        project_id="p",
        release_id="v1.0.0",
        tag="v1.0.0",
        commit_sha="a" * 40,
        effective_at=datetime(2026, 9, 1, tzinfo=UTC),
    )
    pipeline = AsyncMock()
    svc = ReconciliationService(
        client=client, checkpoints=AsyncMock(), pipeline=pipeline, revision_store=store
    )

    await svc.sync_ref("p", "r", "refs/tags/v1.1.0", "0" * 40, "b" * 40)

    release = pipeline.persist.await_args.kwargs["release"]
    assert release.release_id == "v1.1.0"
    assert release.predecessor == "v1.0.0"
    client.changed_files.assert_awaited_once_with("r", "a" * 40, "b" * 40)
    store.set_release_status.assert_any_await("p", "v1.1.0", "ready")
