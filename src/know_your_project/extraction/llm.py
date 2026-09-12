import json

import httpx
from pydantic import BaseModel, Field

from know_your_project.domain.artifacts import FactCandidate
from .models import ParsedArtifact


class _Fact(BaseModel):
    subject: str = Field(min_length=1)
    predicate: str = Field(min_length=1)
    value: str = Field(min_length=1, max_length=2000)
    object_ref: str | None = None
    confidence: float = Field(ge=0.0, le=1.0)


class _Payload(BaseModel):
    facts: list[_Fact]


class LocalKnowledgeExtractor:
    def __init__(self, *, base_url: str, api_key: str, model: str) -> None:
        self._url = base_url.rstrip("/") + "/chat/completions"
        self._key = api_key
        self._model = model

    async def extract(self, parsed: ParsedArtifact) -> list[FactCandidate]:
        instruction = (
            "Extract semantic project facts only. Do not quote or reproduce source code. "
            "Use stable subjects and predicates. Return JSON object {facts:[...]}; each fact has "
            "subject,predicate,value,object_ref,confidence. Values describe behavior, responsibility, "
            "requirement, dependency, screen semantics, or business rules."
        )
        async with httpx.AsyncClient(timeout=90) as client:
            response = await client.post(
                self._url,
                headers={"Authorization": f"Bearer {self._key}"},
                json={
                    "model": self._model,
                    "temperature": 0,
                    "response_format": {"type": "json_object"},
                    "messages": [
                        {"role": "system", "content": instruction},
                        {"role": "user", "content": f"{parsed.title}\n{parsed.semantic_text}"},
                    ],
                },
            )
            response.raise_for_status()
        payload = _Payload.model_validate(
            json.loads(response.json()["choices"][0]["message"]["content"])
        )
        return [
            FactCandidate(
                subject=f.subject,
                predicate=f.predicate,
                value=f.value,
                object_ref=f.object_ref,
                confidence=f.confidence,
                provenance=parsed.provenance,
            )
            for f in payload.facts
        ]
