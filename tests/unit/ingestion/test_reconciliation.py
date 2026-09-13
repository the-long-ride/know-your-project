from unittest.mock import AsyncMock

from know_your_project.ingestion.reconciliation import ReconciliationService


async def test_markdown_and_html_are_classified_before_pipeline() -> None:
    client = AsyncMock()
    client.changed_files.return_value = [
        type("C", (), {"path": "/docs/spec.md", "change_type": "edit"})(),
        type("C", (), {"path": "/mockups/retry.html", "change_type": "edit"})(),
    ]
    client.file_text.side_effect = ["# Spec", "<button>Retry</button>"]
    svc = ReconciliationService(client=client, checkpoints=AsyncMock(), pipeline=AsyncMock())
    artifacts = await svc.collect_git_artifacts("p", "r", "a" * 40, "b" * 40)
    assert [a.kind for a in artifacts] == ["document", "html"]


async def test_deleted_source_is_emitted_as_deleted_artifact_without_fetching_content() -> None:
    client = AsyncMock()
    client.changed_files.return_value = [
        type("C", (), {"path": "/src/OldService.cs", "change_type": "delete"})(),
    ]
    svc = ReconciliationService(client=client, checkpoints=AsyncMock(), pipeline=AsyncMock())
    artifacts = await svc.collect_git_artifacts("p", "r", "a" * 40, "b" * 40)
    assert len(artifacts) == 1
    assert artifacts[0].deleted is True
    client.file_text.assert_not_awaited()
