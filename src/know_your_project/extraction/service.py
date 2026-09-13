import re

from know_your_project.domain.artifacts import FactCandidate, SourceArtifact
from know_your_project.extraction.llm import LocalKnowledgeExtractor
from know_your_project.extraction.parsers.base import ArtifactParser

_CODE_MARKERS = ("{", "}", ";", "(", ")", "=>")


def _normalized(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip().casefold()


def _normalized_path(text: str) -> str:
    return _normalized(text).replace("\\", "/")


def _is_sensitive_excerpt(value: str, artifact: SourceArtifact) -> bool:
    if len(value) >= 32:
        return True
    return (
        artifact.kind == "source"
        and len(value) >= 12
        and any(token in value for token in _CODE_MARKERS)
    )


def _echoes_raw_content(value: str, artifact: SourceArtifact) -> bool:
    candidate = _normalized(value)
    if not candidate:
        return False

    if artifact.path:
        path = _normalized_path(artifact.path)
        normalized_value = _normalized_path(value)
        basename = path.rsplit("/", 1)[-1]
        if path and path in normalized_value:
            return True
        if basename and basename in normalized_value:
            return True

    raw = _normalized(artifact.content)
    if not raw:
        return False
    if candidate in raw and _is_sensitive_excerpt(candidate, artifact):
        return True

    for line in artifact.content.splitlines():
        excerpt = _normalized(line)
        if (
            excerpt
            and excerpt in candidate
            and _is_sensitive_excerpt(excerpt, artifact)
        ):
            return True
    return False


def _is_safe_fact(fact: FactCandidate, artifact: SourceArtifact) -> bool:
    exposed_fields = (fact.subject, fact.predicate, fact.value, fact.object_ref or "")
    return not any(_echoes_raw_content(value, artifact) for value in exposed_fields)


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
        return [fact for fact in facts if _is_safe_fact(fact, artifact)]
