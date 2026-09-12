from graphiti_core import Graphiti
from graphiti_core.cross_encoder.openai_reranker_client import OpenAIRerankerClient
from graphiti_core.embedder.openai import OpenAIEmbedder, OpenAIEmbedderConfig
from graphiti_core.llm_client.config import LLMConfig
from graphiti_core.llm_client.openai_generic_client import OpenAIGenericClient


def create_graphiti(
    *,
    uri: str,
    user: str,
    password: str,
    base_url: str,
    api_key: str,
    llm_model: str,
    embedding_model: str,
) -> Graphiti:
    llm_config = LLMConfig(
        api_key=api_key,
        model=llm_model,
        small_model=llm_model,
        base_url=base_url,
    )
    llm = OpenAIGenericClient(config=llm_config)
    embedder = OpenAIEmbedder(config=OpenAIEmbedderConfig(
        api_key=api_key,
        embedding_model=embedding_model,
        base_url=base_url,
    ))
    return Graphiti(
        uri,
        user,
        password,
        llm_client=llm,
        embedder=embedder,
        cross_encoder=OpenAIRerankerClient(client=llm.client, config=llm_config),
        store_raw_episode_content=False,
    )
