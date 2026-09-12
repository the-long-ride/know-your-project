import os
import pytest

from know_your_project.knowledge.graphiti.client import create_graphiti


@pytest.mark.skipif(os.getenv("RUN_GRAPHITI_INTEGRATION") != "1", reason="Graphiti integration disabled")
async def test_graphiti_indices_can_be_created() -> None:
    graph = create_graphiti(
        uri=os.environ["NEO4J_URI"], user=os.environ["NEO4J_USER"],
        password=os.environ["NEO4J_PASSWORD"], base_url=os.environ["LOCAL_LLM_BASE_URL"],
        api_key=os.environ["LOCAL_LLM_API_KEY"], llm_model=os.environ["LOCAL_LLM_MODEL"],
        embedding_model=os.environ["LOCAL_EMBEDDING_MODEL"],
    )
    try:
        await graph.build_indices_and_constraints()
    finally:
        await graph.close()
