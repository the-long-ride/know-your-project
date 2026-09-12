from know_your_project.knowledge.graphiti.client import create_graphiti


def test_local_graphiti_reranker_reuses_generic_clients_underlying_http_client() -> None:
    graph = create_graphiti(
        uri="bolt://neo4j:7687",
        user="neo4j",
        password="password",
        base_url="http://llm:11434/v1",
        api_key="local",
        llm_model="gpt-oss:20b",
        embedding_model="embedding",
    )
    assert graph.cross_encoder.client is graph.llm_client.client
