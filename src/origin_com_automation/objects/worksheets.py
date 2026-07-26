"""Dataframe-backed, explicit worksheet transformations."""

from __future__ import annotations

import operator
from dataclasses import dataclass
from typing import Any

import numpy as np
import pandas as pd


class TransformValidationError(ValueError):
    code = "WORKSHEET_TRANSFORM_INVALID"


@dataclass(frozen=True)
class TransformResult:
    action: str
    columns: list[str]
    rows: list[list[Any]]
    input_rows: int
    output_rows: int


ALLOWED_OPTIONS = {
    "sort": {"by", "ascending", "na_position"},
    "filter": {"column", "operator", "value"},
    "deduplicate": {"subset", "keep"},
    "fill_missing": {"columns", "strategy", "value"},
    "transpose": set(),
    "merge": {"right_rows", "right_columns", "on", "how", "validate"},
    "concat": {"other_rows", "other_columns", "axis", "ignore_index"},
    "pivot": {"index", "columns", "values", "aggregation"},
    "melt": {"id_vars", "value_vars", "variable_name", "value_name"},
    "calculated_column": {"name", "left", "operator", "right"},
}

FILTER_OPERATORS = {
    "eq": operator.eq,
    "ne": operator.ne,
    "gt": operator.gt,
    "ge": operator.ge,
    "lt": operator.lt,
    "le": operator.le,
}

ARITHMETIC_OPERATORS = {
    "add": operator.add,
    "subtract": operator.sub,
    "multiply": operator.mul,
    "divide": operator.truediv,
    "power": operator.pow,
}


def _records(frame: pd.DataFrame) -> list[list[Any]]:
    result: list[list[Any]] = []
    for row in frame.itertuples(index=False, name=None):
        result.append(
            [
                None
                if value is None or (not isinstance(value, (list, dict)) and pd.isna(value))
                else value.item() if isinstance(value, np.generic) else value
                for value in row
            ]
        )
    return result


def _frame(rows: list[list[Any]], columns: list[str]) -> pd.DataFrame:
    if not columns or len(set(columns)) != len(columns):
        raise TransformValidationError("columns must be non-empty and unique")
    if any(len(row) != len(columns) for row in rows):
        raise TransformValidationError("every row must match the column count")
    return pd.DataFrame(rows, columns=columns)


def transform_table(
    rows: list[list[Any]],
    columns: list[str],
    *,
    action: str,
    options: dict[str, Any] | None = None,
) -> TransformResult:
    normalized_action = action.strip().lower()
    if normalized_action not in ALLOWED_OPTIONS:
        raise TransformValidationError(f"unsupported worksheet transform: {action}")
    opts = dict(options or {})
    unknown = sorted(set(opts) - ALLOWED_OPTIONS[normalized_action])
    if unknown:
        raise TransformValidationError(
            f"unknown options for {normalized_action}: {', '.join(unknown)}"
        )
    frame = _frame(rows, columns)
    input_rows = len(frame)

    try:
        if normalized_action == "sort":
            by = opts.get("by")
            if not isinstance(by, list) or not by:
                raise TransformValidationError("sort requires a non-empty by list")
            frame = frame.sort_values(
                by=by,
                ascending=opts.get("ascending", True),
                na_position=opts.get("na_position", "last"),
            )
        elif normalized_action == "filter":
            operation_name = str(opts.get("operator", ""))
            operation = FILTER_OPERATORS.get(operation_name)
            if operation is None:
                raise TransformValidationError("filter operator is not supported")
            column = str(opts.get("column", ""))
            frame = frame[operation(frame[column], opts.get("value"))]
        elif normalized_action == "deduplicate":
            frame = frame.drop_duplicates(
                subset=opts.get("subset"), keep=opts.get("keep", "first")
            )
        elif normalized_action == "fill_missing":
            selected = opts.get("columns")
            if not isinstance(selected, list) or not selected:
                raise TransformValidationError("fill_missing requires columns")
            strategy = opts.get("strategy")
            if strategy == "value":
                if "value" not in opts:
                    raise TransformValidationError("value strategy requires value")
                frame[selected] = frame[selected].fillna(opts["value"])
            elif strategy in {"forward", "backward"}:
                frame[selected] = frame[selected].ffill() if strategy == "forward" else frame[selected].bfill()
            elif strategy in {"mean", "median"}:
                values = frame[selected].mean() if strategy == "mean" else frame[selected].median()
                frame[selected] = frame[selected].fillna(values)
            elif strategy == "drop_rows":
                frame = frame.dropna(subset=selected)
            else:
                raise TransformValidationError("unsupported fill_missing strategy")
        elif normalized_action == "transpose":
            frame = frame.transpose().reset_index()
            frame.columns = ["source_column", *[f"row_{index}" for index in range(input_rows)]]
        elif normalized_action == "merge":
            right = _frame(opts.get("right_rows", []), opts.get("right_columns", []))
            frame = frame.merge(
                right,
                on=opts.get("on"),
                how=opts.get("how", "inner"),
                validate=opts.get("validate", "one_to_one"),
            )
        elif normalized_action == "concat":
            other = _frame(opts.get("other_rows", []), opts.get("other_columns", []))
            frame = pd.concat(
                [frame, other],
                axis=int(opts.get("axis", 0)),
                ignore_index=bool(opts.get("ignore_index", True)),
            )
        elif normalized_action == "pivot":
            frame = frame.pivot_table(
                index=opts.get("index"),
                columns=opts.get("columns"),
                values=opts.get("values"),
                aggfunc=opts.get("aggregation"),
                sort=True,
            ).reset_index()
            frame.columns = [str(item) for item in frame.columns]
        elif normalized_action == "melt":
            frame = frame.melt(
                id_vars=opts.get("id_vars"),
                value_vars=opts.get("value_vars"),
                var_name=opts.get("variable_name", "variable"),
                value_name=opts.get("value_name", "value"),
            )
        else:
            name = str(opts.get("name", "")).strip()
            if not name or name in frame.columns:
                raise TransformValidationError("calculated column name must be new and non-empty")
            operation = ARITHMETIC_OPERATORS.get(str(opts.get("operator", "")))
            if operation is None:
                raise TransformValidationError("calculated column operator is not supported")
            frame[name] = operation(frame[str(opts.get("left"))], frame[str(opts.get("right"))])
    except TransformValidationError:
        raise
    except (KeyError, TypeError, ValueError, pd.errors.MergeError) as exc:
        raise TransformValidationError(str(exc)) from exc

    frame = frame.reset_index(drop=True)
    return TransformResult(
        action=normalized_action,
        columns=[str(value) for value in frame.columns],
        rows=_records(frame),
        input_rows=input_rows,
        output_rows=len(frame),
    )

