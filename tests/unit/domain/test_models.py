from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from know_your_project.domain.artifacts import FactCandidate, Provenance
from know_your_project.domain.ids import ProjectId, ReleaseId
from know_your_project.revisions.models import Release


def test_fact_candidate_rejects_empty_value() -> None:
    with pytest.raises(ValidationError):
        FactCandidate(
            subject="PaymentRetry",
            predicate="max_attempts",
            value="",
            confidence=1.0,
            provenance=Provenance(source_kind="git", source_id="src:payment"),
        )


def test_release_is_bound_to_exact_commit() -> None:
    release = Release(
        project_id=ProjectId("payments"),
        release_id=ReleaseId("v3.8.0"),
        tag="v3.8.0",
        commit_sha="a" * 40,
        effective_at=datetime(2026, 9, 1, tzinfo=UTC),
    )
    assert release.commit_sha == "a" * 40
