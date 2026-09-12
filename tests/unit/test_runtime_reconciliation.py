from types import SimpleNamespace
from unittest.mock import AsyncMock

from know_your_project.app import reconcile_once
from know_your_project.settings import Settings


def settings() -> Settings:
    return Settings(
        azdo_organization="https://dev.azure.com/acme",
        azdo_project="Project",
        azdo_token="token",
        azdo_webhook_secret="hook",
        azdo_repositories="repo-a, repo-b",
        azdo_tracked_refs="refs/heads/main,refs/heads/release",
        azdo_release_tag_prefix="refs/tags/",
        azdo_work_item_types="Product Backlog Item,User Story,Bug",
        reconciliation_interval_seconds=60,
        neo4j_uri="bolt://neo4j:7687",
        neo4j_user="neo4j",
        neo4j_password="password",
        local_llm_base_url="http://llm:11434/v1",
        local_llm_api_key="local",
        local_llm_model="gpt-oss:20b",
        local_embedding_model="embedding",
        mcp_jwt_jwks_uri="https://login.example/jwks",
        mcp_jwt_issuer="https://login.example/",
        mcp_jwt_audience="know-your-project",
    )


def test_sync_settings_parse_comma_separated_values() -> None:
    value = settings()
    assert value.repositories == ("repo-a", "repo-b")
    assert value.tracked_refs == ("refs/heads/main", "refs/heads/release")
    assert value.work_item_types == ("Product Backlog Item", "User Story", "Bug")


async def test_reconcile_once_syncs_repositories_and_work_items() -> None:
    reconciliation = AsyncMock()
    runtime = SimpleNamespace(reconciliation=reconciliation)
    value = settings()
    await reconcile_once(runtime, value)
    assert reconciliation.reconcile_refs.await_count == 2
    reconciliation.reconcile_refs.assert_any_await(
        "Project", "repo-a", set(value.tracked_refs), value.azdo_release_tag_prefix
    )
    reconciliation.reconcile_work_items.assert_awaited_once_with(
        "Project", value.work_item_types
    )
