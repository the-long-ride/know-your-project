from pydantic import BaseModel, Field

from know_your_project.domain.artifacts import Provenance


class ParsedSymbol(BaseModel):
    kind: str
    name: str


class ParsedArtifact(BaseModel):
    title: str
    semantic_text: str = Field(max_length=30000)
    symbols: list[ParsedSymbol] = Field(default_factory=list)
    provenance: Provenance
