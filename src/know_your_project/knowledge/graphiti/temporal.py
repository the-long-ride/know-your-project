from datetime import datetime

from graphiti_core.search.search_filters import ComparisonOperator, DateFilter, SearchFilters


def temporal_filters(as_of: datetime | None) -> SearchFilters:
    if as_of is None:
        return SearchFilters(invalid_at=[[
            DateFilter(comparison_operator=ComparisonOperator.is_null)
        ]])
    return SearchFilters(
        valid_at=[[
            DateFilter(date=as_of, comparison_operator=ComparisonOperator.less_than_equal)
        ]],
        invalid_at=[
            [DateFilter(date=as_of, comparison_operator=ComparisonOperator.greater_than)],
            [DateFilter(comparison_operator=ComparisonOperator.is_null)],
        ],
    )
