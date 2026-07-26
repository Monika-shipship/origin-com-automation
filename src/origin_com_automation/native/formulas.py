"""Safe planning and verified execution of Origin Set Column Values formulas."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

from .common import NativeValidationError


RECALCULATION_MODES = {"none": 0, "auto": 1, "manual": 2}
_WORKSHEET_REF = re.compile(r"^\[[^\]\r\n;\"]+\][^!\[\]\r\n;\"]+$")
_COLUMN_LETTERS = re.compile(r"^[A-Za-z]+$")


def column_letters(index: int) -> str:
    if isinstance(index, bool) or index < 0:
        raise NativeValidationError("column index must be a non-negative integer")
    value = index + 1
    letters = ""
    while value:
        value, remainder = divmod(value - 1, 26)
        letters = chr(ord("A") + remainder) + letters
    return letters


def column_index(column: str | int) -> int:
    if isinstance(column, int) and not isinstance(column, bool):
        if column < 0:
            raise NativeValidationError("column index must be non-negative")
        return column
    text = str(column).strip()
    if not _COLUMN_LETTERS.fullmatch(text):
        raise NativeValidationError(f"invalid formula column: {column!r}")
    value = 0
    for character in text.upper():
        value = value * 26 + ord(character) - ord("A") + 1
    return value - 1


def normalize_worksheet_ref(value: str) -> str:
    normalized = value.strip()
    if normalized.startswith("worksheet_page:"):
        parts = normalized.split(":", 2)
        if len(parts) == 3:
            normalized = f"[{parts[1]}]{parts[2]}"
    if not _WORKSHEET_REF.fullmatch(normalized):
        raise NativeValidationError(f"invalid or unsafe worksheet ref: {value!r}")
    return normalized


def _quoted_labtalk(value: str, *, field: str, allow_empty: bool) -> str:
    if "\x00" in value:
        raise NativeValidationError(f"{field} must not contain a NUL character")
    if not allow_empty and not value.strip():
        raise NativeValidationError(f"{field} must not be empty")
    escaped = (
        value.replace("\\", "\\\\")
        .replace('"', '\\"')
        .replace("\r", "\\r")
        .replace("\n", "\\n")
    )
    return f'"{escaped}"'


@dataclass(frozen=True)
class ColumnFormulaPlan:
    worksheet_ref: str
    column_index: int
    column_name: str
    target_range: str
    formula: str
    before_script: str
    row_start: int
    row_end: int
    expected_formula_range: str
    recalculate_mode: str
    recalculate_value: int
    command: str


def build_column_formula_plan(
    *,
    worksheet_ref: str,
    column: str | int,
    formula: str,
    before_script: str = "",
    row_start: int = 0,
    row_end: int = -1,
    recalculate_mode: str = "auto",
) -> ColumnFormulaPlan:
    safe_worksheet = normalize_worksheet_ref(worksheet_ref)
    safe_column_index = column_index(column)
    safe_column_name = column_letters(safe_column_index)
    if isinstance(row_start, bool) or row_start < 0:
        raise NativeValidationError("row_start must be a non-negative integer")
    if isinstance(row_end, bool) or row_end < -1:
        raise NativeValidationError("row_end must be -1 or a non-negative integer")
    if row_end != -1 and row_end < row_start:
        raise NativeValidationError("row_end must be -1 or greater than or equal to row_start")
    if recalculate_mode not in RECALCULATION_MODES:
        raise NativeValidationError(f"invalid recalculation mode: {recalculate_mode}")

    normalized_formula = formula.strip()
    normalized_script = before_script.strip()
    quoted_formula = _quoted_labtalk(
        normalized_formula, field="formula", allow_empty=False
    )
    quoted_script = _quoted_labtalk(
        normalized_script, field="before_script", allow_empty=True
    )

    if row_start == 0 and row_end == -1:
        formula_range = ""
    elif row_end == -1:
        formula_range = f"[{row_start + 1}:]"
    else:
        formula_range = f"[{row_start + 1}:{row_end + 1}]"
    target_range = f"{safe_worksheet}!{safe_column_name}{formula_range}"
    recalculate_value = RECALCULATION_MODES[recalculate_mode]
    command = (
        f"csetvalue col:={target_range} formula:={quoted_formula} "
        f"script:={quoted_script} recalculate:={recalculate_value};"
    )
    return ColumnFormulaPlan(
        worksheet_ref=safe_worksheet,
        column_index=safe_column_index,
        column_name=safe_column_name,
        target_range=target_range,
        formula=normalized_formula,
        before_script=normalized_script,
        row_start=row_start,
        row_end=row_end,
        expected_formula_range=formula_range,
        recalculate_mode=recalculate_mode,
        recalculate_value=recalculate_value,
        command=command,
    )


def execute_column_formula_plan(
    app: Any,
    column: Any,
    plan: ColumnFormulaPlan,
) -> dict[str, Any]:
    result = app.Execute(plan.command)
    if result is False or result == 0:
        raise NativeValidationError(
            "Origin rejected the Set Column Values operation",
            code="COLUMN_FORMULA_REJECTED",
        )

    formula = str(column.GetStrProp("Formula") or "")
    before_script = str(column.GetStrProp("Script") or "")
    formula_range = str(column.GetStrProp("FormulaRange") or "")
    recalculate_value = int(column.GetNumProp("SVRM"))
    mismatches: list[dict[str, Any]] = []
    for field, expected, actual in (
        ("formula", plan.formula, formula),
        ("before_script", plan.before_script, before_script),
        ("formula_range", plan.expected_formula_range, formula_range),
        ("recalculate_mode", plan.recalculate_value, recalculate_value),
    ):
        if expected != actual:
            mismatches.append({"field": field, "expected": expected, "actual": actual})
    if mismatches:
        raise NativeValidationError(
            f"Origin formula metadata readback did not match: {mismatches}",
            code="COLUMN_FORMULA_UNCONFIRMED",
        )
    return {
        "worksheet_ref": plan.worksheet_ref,
        "column_ref": f"{plan.worksheet_ref}!{plan.column_name}",
        "target_range": plan.target_range,
        "formula": formula,
        "before_script": before_script,
        "formula_range": formula_range,
        "recalculate_mode": plan.recalculate_mode,
        "recalculate_value": recalculate_value,
        "metadata_verified": True,
    }
