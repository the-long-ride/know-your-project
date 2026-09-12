import httpx
import respx

from know_your_project.domain.artifacts import Provenance
from know_your_project.extraction.llm import LocalKnowledgeExtractor
from know_your_project.extraction.models import ParsedArtifact


@respx.mock
async def test_extractor_validates_fact_schema() -> None:
    respx.post("http://llm/v1/chat/completions").mock(return_value=httpx.Response(200, json={
        "choices": [{"message": {"content":
            '{"facts":[{"subject":"PaymentRetry","predicate":"behavior",'
            '"value":"Retries failed payments","confidence":0.9}]}'
        }}]
    }))
    extractor = LocalKnowledgeExtractor(base_url="http://llm/v1", api_key="x", model="gpt-oss:20b")
    facts = await extractor.extract(ParsedArtifact(
        title="PaymentService.cs", semantic_text="method: RetryPayment",
        provenance=Provenance(source_kind="git", source_id="x"),
    ))
    assert facts[0].predicate == "behavior"
