from typing import Any

from graphiti_core.edges import EntityEdge
from graphiti_core.utils.datetime_utils import utc_now
from graphiti_core.nodes import EntityNode

from know_your_project.domain.queries import KnowledgeQuery
from know_your_project.knowledge.dto import KnowledgeResult, SafeProvenance
from know_your_project.revisions.models import GraphMutation, InvalidateFact, UpsertFact
from .ids import entity_uuid
from .temporal import temporal_filters


class GraphitiKnowledgeRepository:
    def __init__(self, graphiti: Any) -> None:
        self._graphiti = graphiti

    async def _get_edge(self, uuid: str) -> EntityEdge:
        return await EntityEdge.get_by_uuid(self._graphiti.driver, uuid)

    async def apply(self, project_id: str, mutations: list[GraphMutation]) -> None:
        for mutation in mutations:
            if isinstance(mutation, InvalidateFact):
                edge = await self._get_edge(mutation.edge_uuid)
                edge.invalid_at = mutation.invalid_at
                edge.expired_at = utc_now()
                await edge.save(self._graphiti.driver)
                continue

            if not isinstance(mutation, UpsertFact):
                raise TypeError(type(mutation))

            fact = mutation.fact
            target_name = fact.object_ref or fact.value
            source = EntityNode(
                uuid=entity_uuid(project_id, fact.subject),
                name=fact.subject,
                group_id=project_id,
                created_at=fact.valid_from,
            )
            target = EntityNode(
                uuid=entity_uuid(project_id, target_name),
                name=target_name,
                group_id=project_id,
                created_at=fact.valid_from,
            )
            await source.generate_name_embedding(self._graphiti.embedder)
            await target.generate_name_embedding(self._graphiti.embedder)
            await source.save(self._graphiti.driver)
            await target.save(self._graphiti.driver)

            edge = EntityEdge(
                uuid=fact.edge_uuid,
                source_node_uuid=source.uuid,
                target_node_uuid=target.uuid,
                name=fact.predicate.upper().replace(" ", "_"),
                group_id=project_id,
                fact=f"{fact.subject} {fact.predicate}: {fact.value}",
                created_at=fact.valid_from,
                valid_at=fact.valid_from,
                invalid_at=fact.valid_to,
                reference_time=fact.valid_from,
                attributes={
                    "artifact_id": str(fact.artifact_id),
                    "source_kind": fact.provenance.source_kind,
                    "source_id": fact.provenance.source_id,
                    "release_id": str(fact.provenance.release_id)
                    if fact.provenance.release_id
                    else "",
                    "confidence": fact.confidence,
                    "scope": fact.scope,
                },
            )
            await edge.generate_embedding(self._graphiti.embedder)
            await edge.save(self._graphiti.driver)

    async def search(self, query: KnowledgeQuery) -> list[KnowledgeResult]:
        edges = await self._graphiti.search(
            query.text,
            group_ids=[str(query.project_id)],
            num_results=min(query.limit * 5, 250),
            search_filter=temporal_filters(query.as_of),
        )
        results: list[KnowledgeResult] = []
        for edge in edges:
            attrs = edge.attributes or {}
            if str(attrs.get("scope", "release")) != query.scope:
                continue
            results.append(KnowledgeResult(
                id=edge.uuid,
                summary=edge.fact,
                score=getattr(edge, "score", None),
                valid_from=edge.valid_at,
                valid_to=edge.invalid_at,
                provenance=[SafeProvenance(
                    source_kind=str(attrs.get("source_kind", "unknown")),
                    source_id=str(attrs.get("source_id", "unknown")),
                    release_id=str(attrs["release_id"]) if attrs.get("release_id") else None,
                )],
            ))
            if len(results) >= query.limit:
                break
        return results
