"""Deterministic row, branch, filter, and helper-range planning."""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from typing import Any


class SelectionPlanError(ValueError):
    code = "WORKFLOW_SELECTION_INVALID"


@dataclass(frozen=True)
class HelperRangePlan:
    logical_id: str
    workbook_ref: str
    column_prefix: str
    cleanup_targets: tuple[str, ...]


@dataclass(frozen=True)
class SelectionPlan:
    ranges: tuple[tuple[int, int], ...]
    order: str
    branch: str
    category_column: str | int | None
    category_values: tuple[str, ...]
    filters: tuple[dict[str, Any], ...]
    missing_rule: str
    requires_helper: bool
    helper: HelperRangePlan | None


_BRANCHES = {"all", "forward", "reverse", "category", "explicit"}
_ORDERS = {"input", "forward", "reverse"}
_MISSING = {"reject", "exclude", "preserve"}
_OPERATORS = {
    "==",
    "!=",
    ">",
    ">=",
    "<",
    "<=",
    "in",
    "not_in",
    "is_missing",
    "is_not_missing",
}
_COLUMN = re.compile(r"^[A-Za-z]+$|^\d+$")


def _normalize_ranges(ranges: list[tuple[int, int]]) -> tuple[tuple[int, int], ...]:
    normalized: list[tuple[int, int]] = []
    for raw_start, raw_end in ranges:
        if isinstance(raw_start, bool) or isinstance(raw_end, bool):
            raise SelectionPlanError("range bounds must be integers")
        start, end = int(raw_start), int(raw_end)
        if start < 0 or end < start:
            raise SelectionPlanError("range bounds must be non-negative and ordered")
        normalized.append((start, end))
    ordered = sorted(normalized)
    for previous, current in zip(ordered, ordered[1:], strict=False):
        if current[0] <= previous[1]:
            raise SelectionPlanError("selection ranges must not overlap")
    return tuple(normalized)


def _normalize_filters(filters: list[dict[str, Any]]) -> tuple[dict[str, Any], ...]:
    normalized: list[dict[str, Any]] = []
    for item in filters:
        unknown = sorted(set(item) - {"column", "operator", "value"})
        if unknown:
            raise SelectionPlanError(f"unknown filter field: {unknown[0]}")
        if "column" not in item or "operator" not in item:
            raise SelectionPlanError("filter requires column and operator")
        column = str(item["column"]).strip()
        if not _COLUMN.fullmatch(column):
            raise SelectionPlanError(f"invalid filter column: {column}")
        operator = str(item["operator"]).strip().lower()
        if operator not in _OPERATORS:
            raise SelectionPlanError(f"unsupported filter operator: {operator}")
        if operator not in {"is_missing", "is_not_missing"} and "value" not in item:
            raise SelectionPlanError(f"filter operator {operator} requires a value")
        normalized.append(
            {"column": item["column"], "operator": operator, "value": item.get("value")}
        )
    return tuple(normalized)


def compile_selection(
    *,
    ranges: list[tuple[int, int]],
    order: str,
    branch: str,
    category_column: str | int | None = None,
    category_values: list[str] | None = None,
    filters: list[dict[str, Any]] | None = None,
    missing_rule: str = "reject",
) -> SelectionPlan:
    normalized_order = order.strip().lower()
    normalized_branch = branch.strip().lower()
    normalized_missing = missing_rule.strip().lower()
    if normalized_order not in _ORDERS:
        raise SelectionPlanError(f"unsupported row order: {order}")
    if normalized_branch not in _BRANCHES:
        raise SelectionPlanError(f"unsupported branch: {branch}")
    if normalized_missing not in _MISSING:
        raise SelectionPlanError(f"unsupported missing-value rule: {missing_rule}")
    normalized_ranges = _normalize_ranges(ranges)
    normalized_filters = _normalize_filters(list(filters or []))
    values = tuple(str(value) for value in (category_values or []))
    if normalized_branch == "category" and (category_column is None or not values):
        raise SelectionPlanError(
            "category branch requires category_column and category_values"
        )
    requires_helper = bool(
        len(normalized_ranges) > 1
        or normalized_filters
        or normalized_order == "reverse"
        or normalized_branch in {"forward", "reverse", "category", "explicit"}
    )
    helper = None
    if requires_helper:
        payload = json.dumps(
            {
                "ranges": normalized_ranges,
                "order": normalized_order,
                "branch": normalized_branch,
                "category_column": category_column,
                "category_values": values,
                "filters": normalized_filters,
                "missing_rule": normalized_missing,
            },
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
        suffix = hashlib.sha256(payload).hexdigest()[:12]
        logical_id = f"helper:__codex_{suffix}"
        helper = HelperRangePlan(
            logical_id=logical_id,
            workbook_ref="[__CodexWorkflow]Selections",
            column_prefix=f"__codex_{suffix}",
            cleanup_targets=(logical_id,),
        )
    return SelectionPlan(
        ranges=normalized_ranges,
        order=normalized_order,
        branch=normalized_branch,
        category_column=category_column,
        category_values=values,
        filters=normalized_filters,
        missing_rule=normalized_missing,
        requires_helper=requires_helper,
        helper=helper,
    )
