import pytest

from origin_com_automation.objects.worksheets import TransformValidationError, transform_table


ROWS = [
    ["a", 2, None],
    ["b", 1, 10.0],
    ["a", 3, 20.0],
]
COLUMNS = ["group", "x", "y"]


def test_sort_filter_and_fill_missing_are_explicit():
    filtered = transform_table(
        ROWS,
        COLUMNS,
        action="filter",
        options={"column": "x", "operator": "gt", "value": 1},
    )
    sorted_result = transform_table(
        filtered.rows,
        filtered.columns,
        action="sort",
        options={"by": ["x"], "ascending": False},
    )
    filled = transform_table(
        sorted_result.rows,
        sorted_result.columns,
        action="fill_missing",
        options={"columns": ["y"], "strategy": "value", "value": 0},
    )
    assert filled.rows == [["a", 3, 20.0], ["a", 2, 0.0]]


def test_fill_missing_requires_a_value_for_value_strategy():
    with pytest.raises(TransformValidationError, match="requires value"):
        transform_table(
            ROWS,
            COLUMNS,
            action="fill_missing",
            options={"columns": ["y"], "strategy": "value"},
        )


def test_pivot_uses_explicit_aggregation():
    result = transform_table(
        [
            ["A", "x", 1],
            ["A", "x", 3],
            ["A", "y", 5],
            ["B", "x", 7],
        ],
        ["sample", "kind", "value"],
        action="pivot",
        options={
            "index": ["sample"],
            "columns": "kind",
            "values": "value",
            "aggregation": "mean",
        },
    )
    assert result.columns == ["sample", "x", "y"]
    assert result.rows[0] == ["A", 2.0, 5.0]


def test_merge_rejects_duplicate_keys_when_validation_is_one_to_one():
    with pytest.raises(TransformValidationError, match="not unique"):
        transform_table(
            [[1, "a"], [1, "b"]],
            ["id", "left"],
            action="merge",
            options={
                "right_rows": [[1, "c"]],
                "right_columns": ["id", "right"],
                "on": ["id"],
                "how": "inner",
                "validate": "one_to_one",
            },
        )


def test_calculated_column_uses_allowlisted_arithmetic_operation():
    result = transform_table(
        [[1, 2], [3, 4]],
        ["a", "b"],
        action="calculated_column",
        options={"name": "sum", "left": "a", "operator": "add", "right": "b"},
    )
    assert result.columns == ["a", "b", "sum"]
    assert result.rows == [[1, 2, 3], [3, 4, 7]]


def test_transform_rejects_unknown_options():
    with pytest.raises(TransformValidationError, match="unknown options"):
        transform_table(ROWS, COLUMNS, action="sort", options={"by": ["x"], "typo": 1})

