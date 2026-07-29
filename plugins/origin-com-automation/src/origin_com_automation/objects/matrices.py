"""Matrix action plans with bounded rectangular blocks."""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any

from .validation import ObjectPlanError, stable_ref


TRANSFORM_COMMANDS = {
    "transpose": "matrix -t;",
    "rotate_90": "matrix -c r;",
    "flip_horizontal": "matrix -c h;",
    "flip_vertical": "matrix -c v;",
}


@dataclass(frozen=True)
class MatrixPlan:
    action: str
    matrix_ref: str
    values: tuple[tuple[float | None, ...], ...] | None
    row: int
    column: int
    shape: tuple[int, int] | None
    expected_range: tuple[int, int, int, int] | None
    operation: str | None
    command: str | None


def build_matrix_plan(
    *,
    action: str,
    matrix_ref: str,
    values: list[list[Any]] | None = None,
    row: int = 0,
    column: int = 0,
    operation: str | None = None,
    max_cells: int = 1_000_000,
) -> MatrixPlan:
    normalized_action = action.strip().lower()
    if normalized_action not in {"create", "read", "write", "transform"}:
        raise ObjectPlanError("matrix action must be create, read, write, or transform")
    target = stable_ref(matrix_ref, kind="matrix ref")
    if row < 0 or column < 0:
        raise ObjectPlanError("matrix offsets must be non-negative")
    normalized_values = None
    shape = None
    expected_range = None
    if normalized_action == "write":
        if not values or not values[0]:
            raise ObjectPlanError("matrix write requires values")
        width = len(values[0])
        if any(len(item) != width for item in values):
            raise ObjectPlanError("matrix values must be rectangular")
        if len(values) * width > max_cells:
            raise ObjectPlanError("matrix payload exceeds cell limit")
        rows: list[tuple[float | None, ...]] = []
        for source_row in values:
            target_row: list[float | None] = []
            for value in source_row:
                if value is None:
                    target_row.append(None)
                else:
                    number = float(value)
                    if not math.isfinite(number):
                        raise ObjectPlanError("matrix values must be finite or null")
                    target_row.append(number)
            rows.append(tuple(target_row))
        normalized_values = tuple(rows)
        shape = (len(rows), width)
        expected_range = (row, column, row + len(rows) - 1, column + width - 1)
    elif values is not None:
        raise ObjectPlanError(f"matrix {normalized_action} does not accept values")
    command = None
    if normalized_action == "transform":
        if operation not in TRANSFORM_COMMANDS:
            raise ObjectPlanError("matrix transform operation is not supported")
        command = TRANSFORM_COMMANDS[operation]
    elif operation is not None:
        raise ObjectPlanError(f"matrix {normalized_action} does not accept operation")
    return MatrixPlan(
        action=normalized_action,
        matrix_ref=target,
        values=normalized_values,
        row=row,
        column=column,
        shape=shape,
        expected_range=expected_range,
        operation=operation,
        command=command,
    )

