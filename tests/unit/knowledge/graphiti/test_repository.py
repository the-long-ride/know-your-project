from datetime import UTC, datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock

from know_your_project.domain.ids import ProjectId
from know_your_project.domain.queries import KnowledgeQuery
from know_your_project.knowledge.graphiti.repository import GraphitiKnowledgeRepository
from know_your_project.revisions.models import InvalidateFact


async def test_invalidation_updates_exact_edge_only() -> None:
    graphiti = AsyncMock()
    graphiti.driver = object()
    repo = GraphitiKnowledgeRepository(graphiti)
    edge = AsyncMock()
    edge.invalid_at = None
    edge.expired_at = None
    repo._get_edge = AsyncMock(return_value=edge)  # type: ignore[method-assign]
    at = datetime(2026, 9, 2, tzinfo=UTC)
    await repo.apply("payments", [InvalidateFact(edge_uuid="edge-1", invalid_at=at)])
    assert edge.invalid_at == at
    edge.save.assert_awaited_once()


async def test_search_projects_graph_edge_to_safe_result() -> None:
    graphiti = AsyncMock()
    graphiti.search.return_value = [SimpleNamespace(
        uuid="e1",
        fact="PaymentRetry behavior: retries failed payments",
        score=0.9,
        valid_at=datetime(2026, 9, 1, tzinfo=UTC),
        invalid_at=None,
        attributes={"source_kind": "git", "source_id": "git:r:/Payment.cs", "release_id": "v1"},
    )]
    repo = GraphitiKnowledgeRepository(graphiti)
    results = await repo.search(KnowledgeQuery(project_id=ProjectId("p"), text="retry"))
    assert results[0].summary == "PaymentRetry behavior: retries failed payments"
    assert results[0].provenance[0].source_id == "git:r:/Payment.cs"
