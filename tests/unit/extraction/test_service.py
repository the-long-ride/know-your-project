from datetime import UTC, datetime
from unittest.mock import AsyncMock

import pytest

from know_your_project.domain.artifacts import FactCandidate, Provenance, SourceArtifact
from know_your_project.domain.ids import ArtifactId, ProjectId
from know_your_project.extraction.models import ParsedArtifact
from know_your_project.extraction.service import ExtractionService


class _Parser:
    def supports(self, artifact):
        return True

    def parse(self, artifact):
        return ParsedArtifact(
            title=artifact.path or "Secret.cs",
            semantic_text=artifact.content,
            provenance=Provenance(source_kind="git", source_id="secret"),
        )


def _artifact() -> SourceArtifact:
    return SourceArtifact(
        project_id=ProjectId("p"), artifact_id=ArtifactId("secret"), kind="source",
        revision="1",
        content="private void HighlySensitiveImplementationSecret() {}",
        observed_at=datetime.now(UTC), path="/src/private/Secret.cs",
    )


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


@pytest.mark.parametrize("echo_field", ["subject", "predicate", "value", "object_ref"])
async def test_verbatim_source_echo_in_any_public_fact_field_is_rejected(echo_field: str) -> None:
    extractor = AsyncMock()
    fields = {
        "subject": "Payment retry",
        "predicate": "behavior",
        "value": "Retries a failed payment",
        "object_ref": None,
    }
    fields[echo_field] = "private void HighlySensitiveImplementationSecret() {}"
    extractor.extract.return_value = [FactCandidate(
        **fields,
        confidence=1.0,
        provenance=Provenance(source_kind="git", source_id="secret"),
    )]
    service = ExtractionService([_Parser()], extractor)
    assert await service.extract(_artifact()) == []


async def test_internal_source_path_echo_is_rejected() -> None:
    extractor = AsyncMock()
    extractor.extract.return_value = [FactCandidate(
        subject="Payment retry",
        predicate="implemented_in",
        value="Implemented in /src/private/Secret.cs",
        confidence=1.0,
        provenance=Provenance(source_kind="git", source_id="secret"),
    )]
    service = ExtractionService([_Parser()], extractor)
    assert await service.extract(_artifact()) == []


async def test_internal_source_basename_echo_is_rejected() -> None:
    extractor = AsyncMock()
    extractor.extract.return_value = [FactCandidate(
        subject="Payment retry",
        predicate="implemented_in",
        value="Implemented in Secret.cs",
        confidence=1.0,
        provenance=Provenance(source_kind="git", source_id="secret"),
    )]
    service = ExtractionService([_Parser()], extractor)
    assert await service.extract(_artifact()) == []


async def test_prefixed_verbatim_source_excerpt_is_rejected() -> None:
    extractor = AsyncMock()
    extractor.extract.return_value = [FactCandidate(
        subject="Payment retry",
        predicate="implementation",
        value="Implementation: private void HighlySensitiveImplementationSecret() {}",
        confidence=1.0,
        provenance=Provenance(source_kind="git", source_id="secret"),
    )]
    service = ExtractionService([_Parser()], extractor)
    assert await service.extract(_artifact()) == []
