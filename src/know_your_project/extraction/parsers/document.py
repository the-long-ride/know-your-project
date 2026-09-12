import re

from know_your_project.domain.artifacts import Provenance, SourceArtifact
from know_your_project.extraction.models import ParsedArtifact


class DocumentParser:
    def supports(self, artifact: SourceArtifact) -> bool:
        return artifact.kind == "document"

    def parse(self, artifact: SourceArtifact) -> ParsedArtifact:
        text = re.sub(r"\n{3,}", "\n\n", artifact.content).strip()[:30000]
        return ParsedArtifact(
            title=artifact.path or str(artifact.artifact_id), semantic_text=text,
            provenance=Provenance(
                source_kind="document", source_id=str(artifact.artifact_id), path=artifact.path
            ),
        )
