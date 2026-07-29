"""Stateless worksheet value and range helpers."""

from __future__ import annotations

import math
from typing import Any, Iterable

ORIGIN_DATA_FORMAT_NUMERIC = 0
ORIGIN_DATA_FORMAT_TEXT = 1
ORIGIN_DATA_FORMAT_TEXT_NUMERIC = 9
ORIGIN_MISSING_VALUE = -1.23456789e-300


def is_missing_cell(value: Any) -> bool:
    if value is None:
        return True
    if isinstance(value, str):
        return value == ""
    if isinstance(value, float):
        if math.isnan(value):
            return True
        return math.isclose(value, ORIGIN_MISSING_VALUE, rel_tol=0.0, abs_tol=1e-315)
    return False


def normalize_cell(value: Any) -> Any:
    return None if is_missing_cell(value) else value


def column_profile(values: Iterable[Any]) -> dict[str, int]:
    normalized = [normalize_cell(value) for value in values]
    numeric_count = sum(
        isinstance(value, (int, float)) and not isinstance(value, bool)
        for value in normalized
        if value is not None
    )
    text_count = sum(isinstance(value, str) for value in normalized if value is not None)
    non_empty_count = sum(value is not None for value in normalized)
    return {
        "non_empty_count": non_empty_count,
        "numeric_count": numeric_count,
        "text_count": text_count,
        "missing_count": len(normalized) - non_empty_count,
    }


def column_data_format(values: Iterable[Any]) -> int:
    profile = column_profile(values)
    if profile["text_count"] and profile["numeric_count"]:
        return ORIGIN_DATA_FORMAT_TEXT_NUMERIC
    if profile["text_count"]:
        return ORIGIN_DATA_FORMAT_TEXT
    return ORIGIN_DATA_FORMAT_NUMERIC


def rectangular_values(values: list[list[Any]]) -> tuple[list[list[Any]], int]:
    width = max((len(row) for row in values), default=0)
    return [list(row) + [None] * (width - len(row)) for row in values], width


def cells_equal(expected: Any, actual: Any) -> bool:
    expected = normalize_cell(expected)
    actual = normalize_cell(actual)
    if expected is None or actual is None:
        return expected is actual
    if (
        isinstance(expected, (int, float))
        and not isinstance(expected, bool)
        and isinstance(actual, (int, float))
        and not isinstance(actual, bool)
    ):
        return math.isclose(float(expected), float(actual), rel_tol=1e-12, abs_tol=1e-12)
    return str(expected) == str(actual)


def matrix_mismatches(
    expected: list[list[Any]], actual: list[list[Any]], *, limit: int = 10
) -> list[dict[str, Any]]:
    mismatches: list[dict[str, Any]] = []
    for row_index, row in enumerate(expected):
        for column_index, expected_value in enumerate(row):
            actual_value = (
                actual[row_index][column_index]
                if row_index < len(actual) and column_index < len(actual[row_index])
                else None
            )
            if not cells_equal(expected_value, actual_value):
                mismatches.append(
                    {
                        "row_offset": row_index,
                        "column_offset": column_index,
                        "expected": expected_value,
                        "actual": actual_value,
                    }
                )
                if len(mismatches) >= limit:
                    return mismatches
    return mismatches


def worksheet_reference(identifier: str) -> str:
    if identifier.startswith("worksheet_page:"):
        parts = identifier.split(":", 2)
        if len(parts) == 3:
            return f"[{parts[1]}]{parts[2]}"
    return identifier


def coerce_delimited_cell(value: str) -> Any:
    text = value.strip()
    if text == "":
        return None
    try:
        return int(text)
    except ValueError:
        try:
            return float(text)
        except ValueError:
            return value


def split_header(
    rows: list[list[Any]], has_header: bool | None
) -> tuple[list[str] | None, list[list[Any]]]:
    detected = has_header
    if detected is None:
        detected = False
        if len(rows) >= 2:
            first = rows[0]
            second = rows[1]
            first_has_text = any(isinstance(value, str) and value.strip() for value in first)
            second_values = [value for value in second if value is not None]
            second_is_numeric = bool(second_values) and all(
                isinstance(value, (int, float)) and not isinstance(value, bool)
                for value in second_values
            )
            detected = first_has_text and second_is_numeric
    if not detected or not rows:
        return None, rows
    return ["" if value is None else str(value) for value in rows[0]], rows[1:]
