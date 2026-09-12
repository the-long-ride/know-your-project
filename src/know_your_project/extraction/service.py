from know_your_project.domain.artifacts import FactCandidate, SourceArtifact
from .llm import LocalKnowledgeExtractor
from .parsers.base import ArtifactParser


class ExtractionService:
    def __init__(self, parsers: list[ArtifactParser], extractor: LocalKnowledgeExtractor) -> None:
        self._parsers = parsers
        self._extractor = extractor

    async def extract(self, artifact: SourceArtifact) -> list[FactCandidate]:
        parser = next((p for p in self._parsers if p.supports(artifact)), None)
        if parser is None:
            return []
        return await self._extractor.extract(parser.parse(artifact))
