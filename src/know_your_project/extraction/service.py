import re

from know_your_project.domain.artifacts import FactCandidate, SourceArtifact
from .llm import LocalKnowledgeExtractor
from .parsers.base import ArtifactParser


def _normalized(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip().casefold()


def _echoes_raw_content(value: str, artifact: SourceArtifact) -> bool:
    candidate = _normalized(value)
    raw = _normalized(artifact.content)
    if not candidate or not raw or candidate not in raw:
        return False
    if len(candidate) >= 32:
        return True
    if artifact.kind == "source" and len(candidate) >= 12:
        return any(token in candidate for token in ("{", "}", ";", "(", ")", "=>"))
    return False


class ExtractionService:
    def __init__(self, parsers: list[ArtifactParser], extractor: LocalKnowledgeExtractor) -> None:
        self._parsers = parsers
        self._extractor = extractor

    async def extract(self, artifact: SourceArtifact) -> list[FactCandidate]:
        if artifact.deleted:
            return []
        parser = next((p for p in self._parsers if p.supports(artifact)), None)
        if parser is None:
            return []
        facts = await self._extractor.extract(parser.parse(artifact))
        return [fact for fact in facts if not _echoes_raw_content(fact.value, artifact)]
