"""Conversions and stable object lookup for Origin data objects."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any


def find_object(
    objects: Sequence[Mapping[str, Any]],
    *,
    identifier: str | None = None,
    name: str | None = None,
) -> Mapping[str, Any]:
    if not identifier and not name:
        raise ValueError("identifier or name is required")
    if identifier:
        matches = [item for item in objects if str(item.get("id")) == identifier]
    else:
        matches = [
            item
            for item in objects
            if str(item.get("name")) == name or str(item.get("long_name")) == name
        ]
    if not matches:
        raise LookupError(f"Origin object not found: {identifier or name}")
    if len(matches) > 1:
        raise ValueError(f"Origin object name is ambiguous: {name}")
    return matches[0]


def table_from_com_value(value: Any) -> list[list[Any]]:
    if value is None:
        return []
    if isinstance(value, (list, tuple)):
        if not value:
            return []
        if all(not isinstance(row, (list, tuple)) for row in value):
            return [list(value)]
        return [list(row) if isinstance(row, (list, tuple)) else [row] for row in value]
    return [[value]]
