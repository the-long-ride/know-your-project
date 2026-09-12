from datetime import UTC, datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock

from know_your_project.domain.ids import ProjectId
from know_your_project.domain.queries import KnowledgeQuery
from know_your_project.knowledge.graphiti.repository import GraphitiKnowledgeRepository


async def test_search_excludes_branch_facts_from_release_scope() -> None:
    graphiti = AsyncMock()
    graphiti.search.return_value = [
        SimpleNamespace(
            uuid="branch", fact="branch fact", score=1.0,
            valid_at=datetime(2026, 9, 1, tzinfo=UTC), invalid_at=None,
            attributes={"scope": "branch:refs/heads/main", "source_kind": "git", "source_id": "a"},
        ),
        SimpleNamespace(
            uuid="release", fact="release fact", score=0.9,
            valid_at=datetime(2026, 9, 1, tzinfo=UTC), invalid_at=None,
            attributes={"scope": "release", "source_kind": "git", "source_id": "a"},
        ),
    ]
    repo = GraphitiKnowledgeRepository(graphiti)
    results = await repo.search(KnowledgeQuery(project_id=ProjectId("p"), text="fact"))
    assert [r.id for r in results] == ["release"]
