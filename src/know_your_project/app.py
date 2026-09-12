import asyncio
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from pathlib import Path
from typing import cast

from fastmcp import FastMCP
from graphiti_core import Graphiti

from know_your_project.extraction.llm import LocalKnowledgeExtractor
from know_your_project.extraction.parsers.document import DocumentParser
from know_your_project.extraction.parsers.html import HtmlParser
from know_your_project.extraction.parsers.source import TreeSitterSourceParser
from know_your_project.extraction.parsers.work_item import WorkItemParser
from know_your_project.extraction.service import ExtractionService
from know_your_project.ingestion.azure_devops.client import AzureDevOpsClient
from know_your_project.ingestion.checkpoints import SqliteCheckpointStore
from know_your_project.ingestion.pipeline import IngestionPipeline
from know_your_project.ingestion.reconciliation import ReconciliationService
from know_your_project.ingestion.webhooks import AzureDevOpsWebhookHandler
from know_your_project.knowledge.graphiti.client import create_graphiti
from know_your_project.knowledge.graphiti.repository import GraphitiKnowledgeRepository
from know_your_project.mcp.server import create_mcp
from know_your_project.mcp.tools import KnowledgeTools
from know_your_project.revisions.engine import RevisionEngine
from know_your_project.revisions.queries import ReleaseQueryService
from know_your_project.revisions.store import SqliteRevisionStore
from know_your_project.security.authorization import AuthorizationService
from know_your_project.settings import Settings


@dataclass
class Runtime:
    mcp: FastMCP
    graphiti: Graphiti
    revision_store: SqliteRevisionStore
    checkpoint_store: SqliteCheckpointStore
    reconciliation: ReconciliationService


async def build_runtime(settings: Settings | None = None) -> Runtime:
    settings = settings or Settings()  # type: ignore[call-arg]
    state_path = Path(settings.checkpoint_db)
    state_path.parent.mkdir(parents=True, exist_ok=True)

    revision_store = SqliteRevisionStore(str(state_path))
    checkpoint_store = SqliteCheckpointStore(str(state_path))
    await revision_store.initialize()
    await checkpoint_store.initialize()

    graphiti = create_graphiti(
        uri=settings.neo4j_uri,
        user=settings.neo4j_user,
        password=settings.neo4j_password,
        base_url=str(settings.local_llm_base_url),
        api_key=settings.local_llm_api_key,
        llm_model=settings.local_llm_model,
        embedding_model=settings.local_embedding_model,
    )
    await graphiti.build_indices_and_constraints()
    repository = GraphitiKnowledgeRepository(graphiti)

    extractor = LocalKnowledgeExtractor(
        base_url=str(settings.local_llm_base_url),
        api_key=settings.local_llm_api_key,
        model=settings.local_llm_model,
    )
    extraction = ExtractionService(
        [TreeSitterSourceParser(), HtmlParser(), DocumentParser(), WorkItemParser()],
        extractor,
    )
    pipeline = IngestionPipeline(
        extraction=extraction,
        revision_engine=RevisionEngine(),
        revision_store=revision_store,
        repository=repository,
        checkpoints=checkpoint_store,
    )
    azure = AzureDevOpsClient(
        base_url=str(settings.azdo_organization),
        project=settings.azdo_project,
        token=settings.azdo_token,
    )
    reconciliation = ReconciliationService(
        client=azure,
        checkpoints=checkpoint_store,
        pipeline=pipeline,
        revision_store=revision_store,
    )
    revisions = ReleaseQueryService(repository, revision_store)
    authorization = AuthorizationService()
    tools = KnowledgeTools(revisions=revisions, authorization=authorization)
    webhook_handler = AzureDevOpsWebhookHandler(
        project=settings.azdo_project,
        reconciliation=reconciliation,
    )
    mcp = create_mcp(
        tools=tools,
        jwks_uri=str(settings.mcp_jwt_jwks_uri),
        issuer=settings.mcp_jwt_issuer,
        audience=settings.mcp_jwt_audience,
        webhook_secret=settings.azdo_webhook_secret,
        webhook_handler=webhook_handler,
    )
    return Runtime(
        mcp=mcp,
        graphiti=graphiti,
        revision_store=revision_store,
        checkpoint_store=checkpoint_store,
        reconciliation=reconciliation,
    )


async def main() -> None:
    runtime = await build_runtime()
    try:
        await runtime.mcp.run_async(transport="http", host="0.0.0.0", port=8000)
    finally:
        close_graphiti = cast(Callable[[], Awaitable[None]], runtime.graphiti.close)
        await close_graphiti()


if __name__ == "__main__":
    asyncio.run(main())
