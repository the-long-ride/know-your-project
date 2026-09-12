from datetime import UTC, datetime
from unittest.mock import AsyncMock

from know_your_project.domain.artifacts import SourceArtifact
from know_your_project.domain.ids import ArtifactId, ProjectId
from know_your_project.extraction.service import ExtractionService


async def test_unsupported_binary_is_not_sent_to_llm() -> None:
    extractor = AsyncMock()
    service = ExtractionService([], extractor)
    result = await service.extract(SourceArtifact(
        project_id=ProjectId("p"), artifact_id=ArtifactId("asset"), kind="source",
        revision="1", content="SECRET", observed_at=datetime.now(UTC), path="asset.bin",
    ))
    assert result == []
    extractor.extract.assert_not_called()

async def test_deleted_artifact_is_not_sent_to_llm() -> None:
    extractor = AsyncMock()
    service = ExtractionService([], extractor)
    result = await service.extract(SourceArtifact(
        project_id=ProjectId("p"), artifact_id=ArtifactId("old"), kind="source",
        revision="2", content="", observed_at=datetime.now(UTC), path="Old.cs", deleted=True,
    ))
    assert result == []
    extractor.extract.assert_not_called()

async def test_verbatim_source_echo_is_rejected_before_persistence() -> None:
    from know_your_project.domain.artifacts import FactCandidate, Provenance
    from know_your_project.extraction.models import ParsedArtifact

    class Parser:
        def supports(self, artifact):
            return True

        def parse(self, artifact):
            return ParsedArtifact(
                title="Secret.cs",
                semantic_text=artifact.content,
                provenance=Provenance(source_kind="git", source_id="secret"),
            )

    extractor = AsyncMock()
    extractor.extract.return_value = [FactCandidate(
        subject="SecretService",
        predicate="behavior",
        value="private void HighlySensitiveImplementationSecret() {}",
        confidence=1.0,
        provenance=Provenance(source_kind="git", source_id="secret"),
    )]
    service = ExtractionService([Parser()], extractor)
    artifact = SourceArtifact(
        project_id=ProjectId("p"), artifact_id=ArtifactId("secret"), kind="source",
        revision="1",
        content="private void HighlySensitiveImplementationSecret() {}",
        observed_at=datetime.now(UTC), path="Secret.cs",
    )
    assert await service.extract(artifact) == []
