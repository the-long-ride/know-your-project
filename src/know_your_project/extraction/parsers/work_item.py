from know_your_project.domain.artifacts import Provenance, SourceArtifact
from know_your_project.extraction.models import ParsedArtifact


class WorkItemParser:
    def supports(self, artifact: SourceArtifact) -> bool:
        return artifact.kind == "work_item"

    def parse(self, artifact: SourceArtifact) -> ParsedArtifact:
        return ParsedArtifact(
            title=str(artifact.artifact_id), semantic_text=artifact.content[:30000],
            provenance=Provenance(
                source_kind="work_item", source_id=str(artifact.artifact_id)
            ),
        )
