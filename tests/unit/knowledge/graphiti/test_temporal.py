from datetime import UTC, datetime

from graphiti_core.search.search_filters import ComparisonOperator
from know_your_project.knowledge.graphiti.temporal import temporal_filters


def test_as_of_filter_includes_not_yet_invalidated_edges() -> None:
    at = datetime(2026, 9, 1, tzinfo=UTC)
    filters = temporal_filters(at)
    assert filters.valid_at[0][0].comparison_operator == ComparisonOperator.less_than_equal
    assert filters.invalid_at[0][0].comparison_operator == ComparisonOperator.greater_than
    assert filters.invalid_at[1][0].comparison_operator == ComparisonOperator.is_null
