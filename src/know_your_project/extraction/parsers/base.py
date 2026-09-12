from typing import Protocol

from know_your_project.domain.artifacts import SourceArtifact
from know_your_project.extraction.models import ParsedArtifact


class ArtifactParser(Protocol):
    def supports(self, artifact: SourceArtifact) -> bool: ...
    def parse(self, artifact: SourceArtifact) -> ParsedArtifact: ...
