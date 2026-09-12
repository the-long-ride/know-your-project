from datetime import UTC, datetime
from unittest.mock import AsyncMock

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
