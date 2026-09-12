import httpx
import respx

from know_your_project.domain.artifacts import Provenance
from know_your_project.extraction import llm as llm_module
from know_your_project.extraction.llm import LocalKnowledgeExtractor
from know_your_project.extraction.models import ParsedArtifact


def parsed_artifact() -> ParsedArtifact:
    return ParsedArtifact(
        title="PaymentService.cs", semantic_text="method: RetryPayment",
        provenance=Provenance(source_kind="git", source_id="x"),
    )


@respx.mock
async def test_extractor_validates_fact_schema() -> None:
    respx.post("http://llm/v1/chat/completions").mock(return_value=httpx.Response(200, json={
        "choices": [{"message": {"content":
            '{"facts":[{"subject":"PaymentRetry","predicate":"behavior",'
            '"value":"Retries failed payments","confidence":0.9}]}'
        }}]
    }))
    extractor = LocalKnowledgeExtractor(base_url="http://llm/v1", api_key="x", model="gpt-oss:20b")
    facts = await extractor.extract(parsed_artifact())
    await extractor.aclose()
    assert facts[0].predicate == "behavior"


async def test_extractor_reuses_one_http_transport(monkeypatch) -> None:
    created = []

    class Response:
        def raise_for_status(self) -> None:
            pass

        def json(self):
            return {"choices": [{"message": {"content": '{"facts":[]}'}}]}

    class FakeClient:
        def __init__(self, **kwargs):
            created.append(kwargs)

        async def post(self, *args, **kwargs):
            return Response()

        async def aclose(self) -> None:
            pass

    monkeypatch.setattr(llm_module.httpx, "AsyncClient", FakeClient)
    extractor = LocalKnowledgeExtractor(base_url="http://llm/v1", api_key="x", model="gpt-oss:20b")
    await extractor.extract(parsed_artifact())
    await extractor.extract(parsed_artifact())
    await extractor.aclose()
    assert len(created) == 1
