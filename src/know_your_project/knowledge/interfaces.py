from typing import Protocol

from know_your_project.domain.queries import KnowledgeQuery
from know_your_project.revisions.models import GraphMutation
from .dto import KnowledgeResult


class KnowledgeRepository(Protocol):
    async def apply(self, project_id: str, mutations: list[GraphMutation]) -> None: ...
    async def search(self, query: KnowledgeQuery) -> list[KnowledgeResult]: ...
